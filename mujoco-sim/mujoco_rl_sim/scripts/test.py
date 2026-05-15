def _obs_to_state(x, pitch):
    if x > 0.2:
        x_state = 5
    elif x > 0.1:
        x_state = 4
    elif x > 0.0:
        x_state = 3
    elif x > -0.1:
        x_state = 2
    elif x > -0.2:
        x_state = 1
    else:
        x_state = 0

    if pitch < 0.0:
        pitch_state = 0
    elif pitch < 10.0:
        pitch_state = 1
    elif pitch < 20.0:
        pitch_state = 2
    elif pitch < 30.0:
        pitch_state = 3
    else:
        pitch_state = 4

    return 5 * x_state + pitch_state

for x in range(6):
    for p in range(5):
        print(5 * x + p)