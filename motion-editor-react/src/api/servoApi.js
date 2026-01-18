import { SERVO_DAEMON_URL } from '../constants';

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

/**
 * 複数のサーボを同時に動かす
 */
export async function moveServos(servoAngles, mode = 'logical') {
  const promises = Object.entries(servoAngles).map(([ch, angle]) => 
    moveServo(parseInt(ch), mode, angle)
  );
  
  try {
    await Promise.all(promises);
    return { status: 'ok' };
  } catch (error) {
    throw new Error(`Failed to move servos: ${error.message}`);
  }
}