import { SERVO_DAEMON_URL } from './constants';
import { clamp } from './utils';

/**
 * サーボ情報を取得
 */
export async function fetchServos() {
  const response = await fetch(`${SERVO_DAEMON_URL}/servos`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch servos');
  }
  
  const data = await response.json();
  const servosData = data.servos || [];
  
  // サーボデータを整形
  const formattedServos = servosData.map(servo => {
    console.log("servo:", servo);
    const lastLogical = clamp(
      parseFloat(servo.last_logical ?? servo.default_logical ?? 0),
      servo.logical_lo,
      servo.logical_hi
    );
    const lastPhysical = clamp(
      parseFloat(servo.last_physical ?? servo.default_physical ?? 0),
      servo.physical_min,
      servo.physical_max
    );
    
    return {
      name: servo.name,
      logical_lo: servo.logical_lo,
      logical_hi: servo.logical_hi,
      physical_min: servo.physical_min,
      physical_max: servo.physical_max,
      last_logical: lastLogical,
      last_physical: lastPhysical,
    };
  });
  
  return formattedServos;
}

/**
 * サーボを動かす
 */
export async function moveServo(ch, mode, angle) {
  const response = await fetch(`${SERVO_DAEMON_URL}/set`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      ch: ch,
      mode: mode,
      angle: parseFloat(angle),
    }),
  });
  
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Server error: ${text}`);
  }
  
  return response.json();
}