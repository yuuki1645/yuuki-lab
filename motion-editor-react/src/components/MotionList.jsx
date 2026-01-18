import { useState } from 'react';
import './MotionList.css';

export default function MotionList({ motions, currentMotionId, onSelectMotion, onAddMotion, onDeleteMotion, onRenameMotion }) {
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  
  const handleRenameStart = (motion) => {
    setEditingId(motion.id);
    setEditName(motion.name);
  };
  
  const handleRenameSubmit = (id) => {
    if (editName.trim()) {
      onRenameMotion(id, editName.trim());
    }
    setEditingId(null);
    setEditName('');
  };
  
  const handleRenameCancel = () => {
    setEditingId(null);
    setEditName('');
  };
  
  const handleAddNew = () => {
    const name = prompt('モーション名を入力してください:', '新規モーション');
    if (name) {
      onAddMotion(name);
    }
  };
  
  return (
    <div className="motion-list">
      <div className="motion-list-header">
        <h2>モーション一覧</h2>
        <button onClick={handleAddNew} className="btn-add">+ 追加</button>
      </div>
      
      <ul className="motion-items">
        {motions.map(motion => (
          <li 
            key={motion.id} 
            className={`motion-item ${motion.id === currentMotionId ? 'active' : ''}`}
          >
            {editingId === motion.id ? (
              <div className="motion-item-edit">
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleRenameSubmit(motion.id);
                    if (e.key === 'Escape') handleRenameCancel();
                  }}
                  autoFocus
                />
                <button onClick={() => handleRenameSubmit(motion.id)}>✓</button>
                <button onClick={handleRenameCancel}>✕</button>
              </div>
            ) : (
              <>
                <button
                  className="motion-item-name"
                  onClick={() => onSelectMotion(motion.id)}
                >
                  {motion.name}
                </button>
                <div className="motion-item-actions">
                  <button onClick={() => handleRenameStart(motion)}>編集</button>
                  <button 
                    onClick={() => {
                      if (confirm(`「${motion.name}」を削除しますか？`)) {
                        onDeleteMotion(motion.id);
                      }
                    }}
                    className="btn-delete"
                  >
                    削除
                  </button>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
      
      {motions.length === 0 && (
        <p className="motion-list-empty">モーションがありません</p>
      )}
    </div>
  );
}