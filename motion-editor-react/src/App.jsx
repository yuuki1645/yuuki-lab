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
import { transitionServos } from './api/servoApi';
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
    
  // モーションのdurationを最大時間に制限
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
    seekToTime,  // 追加
  } = useInterpolation(keyframes, motionDuration, 'logical');  // currentMotion?.duration || DEFAULT_MOTION_DURATION を motionDuration に変更

  const handlePlayheadDrag = (time) => {
    seekToTime(time);
  };

  const { servos, loading: servosLoading } = useServos();
  
  const [selectedKeyframeIndex, setSelectedKeyframeIndex] = useState(null);
  const [selectedChannel, setSelectedChannel] = useState(null);

  const handleMoveToInitialPosition = async (motion) => {
    if (!motion || !motion.keyframes || motion.keyframes.length === 0) {
      alert('モーションにキーフレームがありません');
      return;
    }
    
    // 0s時点のキーフレームを取得（最初のキーフレームが0sでない場合もあるので、time=0に最も近いものを探す）
    const initialKeyframe = motion.keyframes.find(kf => kf.time === 0) 
      || motion.keyframes.reduce((prev, curr) => 
          Math.abs(curr.time) < Math.abs(prev.time) ? curr : prev
        );
    
    if (!initialKeyframe || !initialKeyframe.angles) {
      alert('初期キーフレームの角度が設定されていません');
      return;
    }
    
    try {
      // チャンネル番号を文字列キーに変換
      const angles = {};
      Object.entries(initialKeyframe.angles).forEach(([ch, angle]) => {
        if (angle !== undefined && angle !== null) {
          angles[String(ch)] = angle;
        }
      });
      
      if (Object.keys(angles).length === 0) {
        alert('設定可能な角度がありません');
        return;
      }
      
      await transitionServos(angles, 'logical', 3.0);
      alert('初期位置への移動を開始しました');
    } catch (error) {
      console.error('Failed to move to initial position:', error);
      alert(`エラー: ${error.message}`);
    }
  };
  
  // モーションが切り替わったら選択をリセット
  if (currentMotion && selectedKeyframeIndex !== null) {
    if (selectedKeyframeIndex >= keyframes.length) {
      setSelectedKeyframeIndex(null);
      setSelectedChannel(null);
    }
  }
  
  const handleTimeClick = (time, channel) => {
    // チャンネル指定時のみキーフレーム追加（ルーラークリックでは追加しない）
    if (currentMotion && channel !== null) {
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
          onMoveToInitialPosition={handleMoveToInitialPosition}  // 追加
        />
        
        <div className="app-main">
          <Timeline
            keyframes={keyframes}
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