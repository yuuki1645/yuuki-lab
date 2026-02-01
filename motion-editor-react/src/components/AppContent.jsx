// AppContent.jsx（新規）
import { useMotionContext } from '../contexts/MotionContext';
import PlaybackContextProvider from './PlaybackContextProvider';
import MotionList from './MotionList';
import Timeline from './Timeline';
import ServoAngleEditor from './ServoAngleEditor';
import PlaybackControls from './PlaybackControls';

export default function AppContent() {
  const { isInitialized } = useMotionContext();

  if (!isInitialized) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: '#fff' }}>
        読み込み中...
      </div>
    );
  }

  return (
    <PlaybackContextProvider>
      <div className="app-content">
        <MotionList />
        <div className="app-main">
          <Timeline />
          <PlaybackControls />
        </div>
        <ServoAngleEditor />
      </div>
    </PlaybackContextProvider>
  );
}