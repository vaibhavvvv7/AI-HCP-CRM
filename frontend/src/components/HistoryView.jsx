import React, { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { editInteraction } from '../store/crmSlice';
import { Clock, Edit3, MessageSquare, Layers, Award, ShieldAlert, X, Save } from 'lucide-react';

export default function HistoryView() {
  const dispatch = useDispatch();
  const { interactions, selectedHcpId } = useSelector((state) => state.crm);
  
  // State for edit modal
  const [editingLog, setEditingLog] = useState(null);
  const [editChannel, setEditChannel] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [editSentiment, setEditSentiment] = useState('');
  const [editProducts, setEditProducts] = useState('');
  const [editMaterials, setEditMaterials] = useState('');
  const [editSamples, setEditSamples] = useState('');
  const [saving, setSaving] = useState(false);

  const handleOpenEdit = (log) => {
    setEditingLog(log);
    setEditChannel(log.channel);
    setEditNotes(log.notes);
    setEditSentiment(log.sentiment || 'Neutral');
    setEditProducts(log.products_discussed || '');
    setEditMaterials(log.materials_shared || '');
    setEditSamples(log.samples_distributed || '');
  };

  const handleCloseEdit = () => {
    setEditingLog(null);
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editingLog) return;

    setSaving(true);
    const payload = {
      channel: editChannel,
      notes: editNotes,
      sentiment: editSentiment,
      products_discussed: editProducts,
      materials_shared: editMaterials,
      samples_distributed: editSamples
    };

    try {
      await dispatch(editInteraction({ 
        interactionId: editingLog.id, 
        payload, 
        hcpId: selectedHcpId 
      })).unwrap();
      handleCloseEdit();
    } catch (err) {
      alert('Failed to update interaction: ' + err);
    } finally {
      setSaving(false);
    }
  };

  const getSentimentClass = (sentiment) => {
    if (!sentiment) return 'neutral';
    return sentiment.toLowerCase();
  };

  return (
    <div className="history-view-container glass-card">
      <div className="history-header">
        <h3>Interaction Timeline</h3>
        <p className="subtext">Chronological history of contacts & updates</p>
      </div>

      {interactions.length === 0 ? (
        <div className="history-empty">
          <Clock size={32} />
          <p>No interactions logged yet for this HCP.</p>
          <p className="subtext">Use the conversational assistant or the structured form to log your first meeting.</p>
        </div>
      ) : (
        <div className="timeline">
          {interactions.map((log) => (
            <div key={log.id} className="timeline-item">
              <div className="timeline-badge">
                <span className={`channel-indicator ${log.channel.split(' ')[0].toLowerCase()}`}>
                  {log.channel[0]}
                </span>
              </div>
              
              <div className="timeline-content glass-card">
                <div className="timeline-meta">
                  <span className="log-channel">{log.channel}</span>
                  <span className="log-date">{new Date(log.date).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}</span>
                  <span className={`badge sentiment-tag ${getSentimentClass(log.sentiment)}`}>
                    {log.sentiment || 'Neutral'}
                  </span>
                </div>

                <div className="log-body">
                  <div className="log-section">
                    <div className="sec-title">
                      <MessageSquare size={12} />
                      <span>Discussion Notes</span>
                    </div>
                    <p className="raw-notes">{log.notes}</p>
                  </div>

                  {log.summary && (
                    <div className="log-section ai-section">
                      <div className="sec-title">
                        <Award size={12} className="ai-ico" />
                        <span>AI Summarized Efficacy</span>
                      </div>
                      <p className="ai-summary">{log.summary}</p>
                    </div>
                  )}

                  <div className="log-footer-details">
                    {log.products_discussed && log.products_discussed !== 'None' && (
                      <div className="footer-detail-item">
                        <Layers size={12} />
                        <span>Discussed: <strong>{log.products_discussed}</strong></span>
                      </div>
                    )}
                    {log.materials_shared && log.materials_shared.trim() !== '' && (
                      <div className="footer-detail-item">
                        <Award size={12} />
                        <span>Materials: <strong>{log.materials_shared}</strong></span>
                      </div>
                    )}
                    {log.samples_distributed && log.samples_distributed.trim() !== '' && (
                      <div className="footer-detail-item">
                        <Award size={12} />
                        <span>Samples: <strong>{log.samples_distributed}</strong></span>
                      </div>
                    )}
                    {log.next_steps && log.next_steps !== 'None' && (
                      <div className="footer-detail-item">
                        <ShieldAlert size={12} />
                        <span>Next Steps: <strong>{log.next_steps}</strong></span>
                      </div>
                    )}
                  </div>
                </div>

                <button 
                  onClick={() => handleOpenEdit(log)} 
                  className="btn-edit-log secondary-btn"
                  title="Edit Interaction Log"
                >
                  <Edit3 size={12} />
                  <span>Edit Log</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Interaction Modal */}
      {editingLog && (
        <div className="modal-overlay">
          <div className="modal-content glass-card zoom-in">
            <div className="modal-header">
              <h3>Edit Interaction Log (ID: {editingLog.id})</h3>
              <button onClick={handleCloseEdit} className="close-btn">
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="edit-form">
              <div className="form-field">
                <label>Channel</label>
                <select value={editChannel} onChange={(e) => setEditChannel(e.target.value)} required>
                  <option value="Face-to-Face">Face-to-Face</option>
                  <option value="Virtual">Virtual Meeting (Zoom/Teams)</option>
                  <option value="Phone">Phone Call</option>
                  <option value="Email">Email Exchange</option>
                </select>
              </div>

              <div className="form-field">
                <label>Sentiment</label>
                <select value={editSentiment} onChange={(e) => setEditSentiment(e.target.value)}>
                  <option value="Positive">Positive</option>
                  <option value="Neutral">Neutral</option>
                  <option value="Negative">Negative</option>
                </select>
              </div>

              <div className="form-field">
                <label>Products Discussed (Comma-separated)</label>
                <input 
                  type="text" 
                  value={editProducts} 
                  onChange={(e) => setEditProducts(e.target.value)} 
                  placeholder="e.g. Lipitor, Zestril"
                />
              </div>

              <div className="form-field">
                <label>Materials Shared (Comma-separated)</label>
                <input 
                  type="text" 
                  value={editMaterials} 
                  onChange={(e) => setEditMaterials(e.target.value)} 
                  placeholder="e.g. Lipitor Brochure"
                />
              </div>

              <div className="form-field">
                <label>Samples Distributed (Comma-separated)</label>
                <input 
                  type="text" 
                  value={editSamples} 
                  onChange={(e) => setEditSamples(e.target.value)} 
                  placeholder="e.g. Lipitor 10mg"
                />
              </div>

              <div className="form-field">
                <label>Notes & Transcript</label>
                <textarea 
                  value={editNotes} 
                  onChange={(e) => setEditNotes(e.target.value)} 
                  required
                  rows={5}
                />
              </div>

              <div className="modal-actions">
                <button type="button" onClick={handleCloseEdit} className="secondary-btn">Cancel</button>
                <button type="submit" disabled={saving} className="primary-btn">
                  <Save size={14} />
                  <span>{saving ? 'Saving...' : 'Save Changes'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
