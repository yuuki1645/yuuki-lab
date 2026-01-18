import { useState } from 'react';
import { useMotion } from './hooks/useMotion';
import { useKeyframes } from './hooks/useKeyframes';
import { useInterpolation } from './hooks/useInterpolation';
import MotionList from './components/MotionList';
import Timeline from './components/Timeline';
import KeyframeEditor from './components/KeyframeEditor';
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
  } = useMotion();
  
  const {
    keyframes,
    addKeyframe,
    deleteKeyframe,
    updateKeyframeTime,
    updateKeyframeAngles,
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
  } = useInterpolation(keyframes, currentMotion?.duration || 5000, 'logical');
  
  const [selectedKeyframeIndex, setSelectedKeyframeIndex] = useState(null);
  
  // モーションが切り替わったら選択をリセット
  if (currentMotion && selectedKeyframeIndex !== null) {
    if (selectedKeyframeIndex >= keyframes.length) {
      setSelectedKeyframeIndex(null);
    }
  }
  
  // モーションがない場合は新規作成
  if (motions.length === 0) {
    addMotion('デフォルトモーション');
  }
  
  const handleTimeClick = (time) => {
    if (currentMotion) {
      addKeyframe(time);
    }
  };
  
  const handleKeyframeClick = (index) => {
    setSelectedKeyframeIndex(index);
  };
  
  const handleKeyframeDrag = (index, newTime) => {
    updateKeyframeTime(index, newTime);
  };
  
  const selectedKeyframe = selectedKeyframeIndex !== null 
    ? keyframes[selectedKeyframeIndex] 
    : null;
  
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
            duration={currentMotion?.duration || 5000}
            currentTime={currentTime}
            onTimeClick={handleTimeClick}
            onKeyframeClick={handleKeyframeClick}
            onKeyframeDrag={handleKeyframeDrag}
            selectedKeyframeIndex={selectedKeyframeIndex}
          />
          
          <PlaybackControls
            isPlaying={isPlaying}
            isPaused={isPaused}
            currentTime={currentTime}
            duration={currentMotion?.duration || 5000}
            loop={loop}
            playbackSpeed={playbackSpeed}
            onPlay={play}
            onPause={pause}
            onStop={stop}
            onLoopChange={setLoop}
            onPlaybackSpeedChange={setPlaybackSpeed}
          />
        </div>
        
        <KeyframeEditor
          keyframe={selectedKeyframe}
          keyframeIndex={selectedKeyframeIndex}
          onUpdateAngle={updateKeyframeAngles}
          onDelete={(index) => {
            deleteKeyframe(index);
            setSelectedKeyframeIndex(null);
          }}
        />
      </div>
    </div>
  );
}

export default App;