# type: ignore

import smbus2
import time
import math
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

# ==========================================
#  MPU6050 Functions
# ==========================================

MPU_ADDR = 0x68
bus = smbus2.SMBus(1)

def mpu_init():
    bus.write_byte_data(MPU_ADDR, 0x6B, 0)

def read_word(reg):
    high = bus.read_byte_data(MPU_ADDR, reg)
    low = bus.read_byte_data(MPU_ADDR, reg + 1)
    val = (high << 8) + low
    if val >= 0x8000:
        val = -((65535 - val) + 1)
    return val

def get_gyro():
    gx = read_word(0x43) / 131.0
    gy = read_word(0x45) / 131.0
    gz = read_word(0x47) / 131.0
    return gx, gy, gz

def get_accel():
    ax = read_word(0x3B) / 16384.0
    ay = read_word(0x3D) / 16384.0
    az = read_word(0x3F) / 16384.0
    return ax, ay, az

# ==========================================
#  Complementary Filter
# ==========================================

pitch, roll, yaw = 0.0, 0.0, 0.0
alpha = 0.98

count = 0

def update_angles(dt):
    global pitch, roll, yaw
    global count

    ax, ay, az = get_accel()
    gx, gy, gz = get_gyro()

    count += 1
    if count == 10:
        # print(f"gx={gx:>6.0f}, gy={gy:>6.0f}, gz={gz:>6.0f}")
        length = math.sqrt(ax**2 + ay**2 + az**2)
        print(f"len={length:>6.2f}, ax={ax:>6.2f}, ay={ay:>6.2f}, az={az:>6.2f}")
        count = 0

    acc_pitch = math.degrees(math.atan2(ay, math.sqrt(ax*ax + az*az)))
    acc_roll  = math.degrees(math.atan2(-ax, math.sqrt(ay*ay + az*az)))

    pitch = alpha * (pitch + gx * dt) + (1 - alpha) * acc_pitch
    roll  = alpha * (roll  + gy * dt) + (1 - alpha) * acc_roll
    yaw  += gz * dt

    return pitch, roll, yaw

# ==========================================
#  Airplane model
# ==========================================

airplane_vertices = [
    [0, 0, 1],
    [-0.5, 0.2, -1],
    [0.5, 0.2, -1],
    [0.5, -0.2, -1],
    [-0.5, -0.2, -1],
    [-2, 0, -0.5],
    [2, 0, -0.5],
]

airplane_edges = [
    (0,1), (0,2), (0,3), (0,4),
    (1,2), (2,3), (3,4), (4,1),
    (1,5), (4,5),
    (2,6), (3,6),
]

def draw_airplane():
    glColor3f(1.0, 1.0, 1.0)
    glBegin(GL_LINES)
    for edge in airplane_edges:
        for v in edge:
            glVertex3fv(airplane_vertices[v])
    glEnd()

# ==========================================
#  OpenGL Init
# ==========================================

def init_display():
    pygame.init()
    display = (900, 700)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)

    glEnable(GL_DEPTH_TEST)
    glClearColor(0, 0, 0, 1)

    # ---- Projection Matrix ----
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, display[0] / display[1], 0.1, 50.0)

    # ---- ModelView Matrix ----
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()


# ==========================================

def main():
    mpu_init()
    init_display()

    clock = pygame.time.Clock()

    while True:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

        pitch, roll, yaw = update_angles(dt)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # カメラを後方に
        glTranslatef(0, 0, -8)

        # 飛行機の姿勢
        glRotatef(-roll, 0, 0, 1)
        glRotatef(-pitch, 1, 0, 0)
        glRotatef(-yaw, 0, 1, 0)

        draw_airplane()

        pygame.display.flip()


if __name__ == "__main__":
    main()
