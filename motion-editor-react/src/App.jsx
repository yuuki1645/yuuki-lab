// App.jsx
import MotionContextProvider from './components/MotionContextProvider';
import AppContent from './components/AppContent';
import './App.css';

function App() {
  return (
    <div className="app">
      <div className="app-header">
        <h1>モーションエディタ</h1>
      </div>
      <MotionContextProvider>
        <AppContent />
      </MotionContextProvider>
    </div>
  );
}

export default App;