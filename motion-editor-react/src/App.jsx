import { useState, useRef, useEffect } from 'react';
import { useMotion } from './hooks/useMotion';
import { useKeyframes } from './hooks/useKeyframes';
import { useInterpolation } from './hooks/useInterpolation';
import { useServos } from './hooks/useServos';
import { MAX_MOTION_DURATION, DEFAULT_MOTION_DURATION, SERVO_CHANNELS } from './constants';
import { getAngleAtTime } from './utils/interpolation';
import MotionList from './components/MotionList';
import Timeline from './components/Timeline';
import ServoAngleEditor from './components/ServoAngleEditor';
import PlaybackControls from './components/PlaybackControls';
import { transitionServos } from './api/servoApi';
import './App.css';

// main

function App() {
  const {
    motions,
    currentMotion,
    currentMotionId,
    setCurrentMotionId,
    addMotion,
    deleteMotion,
    updateMotion,
    renameMotion,
    isInitialized,
  } = useMotion();

  const {
    keyframes,
    addKeyframe,
    deleteKeyframe,
    updateKeyframeTime,
    updateKeyframeAngle,
  } = useKeyframes(currentMotion, updateMotion);

  const motionDuration = currentMotion
    ? Math.min(currentMotion.duration, MAX_MOTION_DURATION)
    : DEFAULT_MOTION_DURATION;

  const {
    isPlaying,
    isPaused,
    currentTime,
    loop,
    playbackSpeed,
    setLoop,
    setPlaybackSpeed,
    play,
    pause,
    stop,
    seekToTime,
  } = useInterpolation(keyframes, motionDuration, 'logical');

  const { servos, loading: servosLoading } = useServos();

  const [selectedKeyframeId, setSelectedKeyframeId] = useState(null);

  const endKeyframeDragRef = useRef(null);

  // 選択中キーフレームが keyframes から消えたら選択を外す
  useEffect(() => {
    if (currentMotion && selectedKeyframeId !== null) {
      const exists = keyframes.some((kf) => kf.id === selectedKeyframeId);
      if (!exists) {
        setSelectedKeyframeId(null);
      }
    }
  }, [currentMotion, selectedKeyframeId, keyframes]);

  const handleMoveToInitialPosition = async (motion) => {
    if (!motion || !motion.keyframes || motion.keyframes.length === 0) {
      alert('モーションにキーフレームがありません');
      return;
    }
    const angles = getAngleAtTime(motion.keyframes, 0, SERVO_CHANNELS);
    const angleEntries = Object.entries(angles).filter(
      ([_, angle]) => angle !== undefined && angle !== null
    );
    if (angleEntries.length === 0) {
      alert('設定可能な角度がありません');
      return;
    }
    const anglesObj = Object.fromEntries(
      angleEntries.map(([ch, angle]) => [String(ch), angle])
    );
    try {
      await transitionServos(anglesObj, 'logical', 3.0);
      alert('初期位置への移動を開始しました');
    } catch (error) {
      console.error('Failed to move to initial position:', error);
      alert(`エラー: ${error.message}`);
    }
  };

  const handleTimeClick = (time, channel) => {
    if (currentMotion && channel !== null) {
      addKeyframe(time, channel);
    }
  };

  const handleKeyframeClick = (id) => {
    setSelectedKeyframeId(id);
  };

  const handleKeyframeDrag = (id, newTime) => {
    updateKeyframeTime(id, newTime);
  };

  const handleAngleUpdate = (keyframeId, angle) => {
    updateKeyframeAngle(keyframeId, angle);
  };

  const handleKeyframeDelete = (keyframeId) => {
    deleteKeyframe(keyframeId);
    setSelectedKeyframeId(null);
  };

  const selectedKeyframe = selectedKeyframeId !== null
    ? keyframes.find((kf) => kf.id === selectedKeyframeId) ?? null
    : null;

  const selectedChannel = selectedKeyframe?.channel ?? null;
  const selectedServo = selectedChannel !== null
    ? servos.find((s) => s.ch === selectedChannel)
    : null;

  if (!isInitialized) {
    return (
      <div className="app">
        <div className="app-header">
          <h1>モーションエディタ</h1>
        </div>
        <div style={{ padding: '20px', textAlign: 'center', color: '#fff' }}>
          読み込み中...
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="app-header">
        <h1>モーションエディタ</h1>
      </div>

      <div className="app-content">
        <MotionList
          motions={motions}
          currentMotionId={currentMotionId}
          onSelectMotion={setCurrentMotionId}
          onAddMotion={addMotion}
          onDeleteMotion={deleteMotion}
          onRenameMotion={renameMotion}
          onMoveToInitialPosition={handleMoveToInitialPosition}
        />

        <div className="app-main">
          <Timeline
            keyframes={keyframes}
            currentTime={currentTime}
            onTimeClick={handleTimeClick}
            onKeyframeClick={handleKeyframeClick}
            onKeyframeDrag={handleKeyframeDrag}
            selectedKeyframeId={selectedKeyframeId}
            onPlayheadDrag={seekToTime}
            endKeyframeDragRef={endKeyframeDragRef}
          />

          <PlaybackControls
            isPlaying={isPlaying}
            isPaused={isPaused}
            currentTime={currentTime}
            duration={motionDuration}
            loop={loop}
            playbackSpeed={playbackSpeed}
            onPlay={play}
            onPause={pause}
            onStop={stop}
            onLoopChange={setLoop}
            onPlaybackSpeedChange={setPlaybackSpeed}
          />
        </div>

        <ServoAngleEditor
          keyframe={selectedKeyframe}
          keyframeId={selectedKeyframeId}
          channel={selectedChannel}
          servo={selectedServo}
          onUpdateAngle={handleAngleUpdate}
          onDelete={handleKeyframeDelete}
          endKeyframeDragRef={endKeyframeDragRef}
        />
      </div>
    </div>
  );
}

export default App;