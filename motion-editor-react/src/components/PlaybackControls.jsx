import { usePlaybackContext } from '../contexts/PlaybackContext';
import './PlaybackControls.css';

export default function PlaybackControls() {
  const {
    isPlaying,
    isPaused,
    currentTime,
    duration,
    loop,
    playbackSpeed,
    play,
    pause,
    stop,
    setLoop,
    setPlaybackSpeed,
  } = usePlaybackContext();

  const formatTime = (ms) => {
    const seconds = (ms / 1000).toFixed(2);
    return `${seconds}s`;
  };

  return (
    <div className="playback-controls">
      <div className="playback-controls-main">
        <button
          onClick={isPlaying ? pause : play}
          className="btn-play-pause"
          type="button"
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
        <button onClick={stop} className="btn-stop" type="button">
          ⏹
        </button>
        <div className="playback-time">
          <span>{formatTime(currentTime)}</span>
          <span className="playback-time-separator">/</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>

      <div className="playback-controls-options">
        <label className="playback-option">
          <input
            type="checkbox"
            checked={loop}
            onChange={(e) => setLoop(e.target.checked)}
            className="playback-checkbox"
          />
          <span>ループ</span>
        </label>
        <label className="playback-option">
          <span>速度:</span>
          <input
            type="range"
            min="0.25"
            max="2"
            step="0.25"
            value={playbackSpeed}
            onChange={(e) => setPlaybackSpeed(parseFloat(e.target.value))}
            className="playback-speed-slider"
          />
          <span>{playbackSpeed.toFixed(2)}x</span>
        </label>
      </div>
    </div>
  );
}