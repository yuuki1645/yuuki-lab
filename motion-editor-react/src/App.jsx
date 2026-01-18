import { useState } from 'react';
import { useMotion } from './hooks/useMotion';
import { useKeyframes } from './hooks/useKeyframes';
import { useInterpolation } from './hooks/useInterpolation';
import { useServos } from './hooks/useServos';
import { SERVO_NAME_TO_CH } from './constants';
import { MAX_MOTION_DURATION, DEFAULT_MOTION_DURATION } from './constants';
import MotionList from './components/MotionList';
import Timeline from './components/Timeline';
import ServoAngleEditor from './components/ServoAngleEditor';
import PlaybackControls from './components/PlaybackControls';
import './App.css';

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
    seekToTime,  // 追加
  } = useInterpolation(keyframes, currentMotion?.duration || DEFAULT_MOTION_DURATION, 'logical');
  
  const handlePlayheadDrag = (time) => {
    seekToTime(time);
  };

  const { servos, loading: servosLoading } = useServos();
  
  const [selectedKeyframeIndex, setSelectedKeyframeIndex] = useState(null);
  const [selectedChannel, setSelectedChannel] = useState(null);
  
  // モーションが切り替わったら選択をリセット
  if (currentMotion && selectedKeyframeIndex !== null) {
    if (selectedKeyframeIndex >= keyframes.length) {
      setSelectedKeyframeIndex(null);
      setSelectedChannel(null);
    }
  }
  
  const handleTimeClick = (time, channel) => {
    if (currentMotion) {
      addKeyframe(time, channel);
    }
  };
  
  const handleKeyframeClick = (index, channel) => {
    console.log("handleKeyframeClick", index, channel);
    setSelectedKeyframeIndex(index);
    setSelectedChannel(channel); // これを追加
  };
  
  const handleKeyframeDrag = (index, newTime) => {
    updateKeyframeTime(index, newTime);
  };
  
  const handleAngleUpdate = (keyframeIndex, channel, angle) => {
    updateKeyframeAngle(keyframeIndex, channel, angle);
  };
  
  const handleKeyframeDelete = (index) => {
    deleteKeyframe(index);
    setSelectedKeyframeIndex(null);
    setSelectedChannel(null);
  };
  
  const selectedKeyframe = selectedKeyframeIndex !== null 
    ? keyframes[selectedKeyframeIndex] 
    : null;
  
  // 選択されたチャンネルのサーボ情報を取得
  const selectedServo = selectedChannel !== null
    ? servos.find(s => s.ch === selectedChannel)
    : null;
  
  // 初期化中はローディング表示
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
  
  // モーションのdurationを最大時間に制限
  const motionDuration = currentMotion 
    ? Math.min(currentMotion.duration, MAX_MOTION_DURATION)
    : DEFAULT_MOTION_DURATION;
  
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
        />
        
        <div className="app-main">
          <Timeline
            keyframes={keyframes}
            duration={motionDuration}
            currentTime={currentTime}
            onTimeClick={handleTimeClick}
            onKeyframeClick={handleKeyframeClick}
            onKeyframeDrag={handleKeyframeDrag}
            selectedKeyframeIndex={selectedKeyframeIndex}
            selectedChannel={selectedChannel}
            onPlayheadDrag={handlePlayheadDrag}  // 追加
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
          keyframeIndex={selectedKeyframeIndex}
          channel={selectedChannel}
          servo={selectedServo}
          onUpdateAngle={handleAngleUpdate}
          onDelete={handleKeyframeDelete}
        />
      </div>
    </div>
  );
}

export default App;