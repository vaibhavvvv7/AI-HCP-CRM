import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { selectHcp, seedDatabase, fetchHcps, fetchInteractions, fetchTasks } from '../store/crmSlice';
import { Stethoscope, Building2, Mail, Phone, MapPin, Database, Smile, Meh, Frown } from 'lucide-react';

export default function HcpSelector() {
  const dispatch = useDispatch();
  const { hcps, selectedHcpId, loading } = useSelector((state) => state.crm);

  const handleSelectHcp = (id) => {
    dispatch(selectHcp(id));
    dispatch(fetchInteractions(id));
    dispatch(fetchTasks(id));
  };

  const handleSeed = async () => {
    await dispatch(seedDatabase());
    const result = await dispatch(fetchHcps());
    const freshHcps = result.payload;
    if (Array.isArray(freshHcps) && freshHcps.length > 0) {
      const firstHcp = freshHcps[0].id;
      dispatch(selectHcp(firstHcp));
      dispatch(fetchInteractions(firstHcp));
      dispatch(fetchTasks(firstHcp));
    }
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case 'Positive':
        return <Smile className="sent-icon pos" size={16} />;
      case 'Negative':
        return <Frown className="sent-icon neg" size={16} />;
      default:
        return <Meh className="sent-icon neu" size={16} />;
    }
  };

  const selectedHcp = hcps.find((h) => h.id === selectedHcpId);

  return (
    <aside className="hcp-selector-sidebar glass-panel">
      <div className="sidebar-header">
        <h2>HCP Directory</h2>
        <button onClick={handleSeed} className="btn-seed secondary-btn" title="Seed Demo Database">
          <Database size={14} />
          <span>Seed Demo Data</span>
        </button>
      </div>

      {loading && hcps.length === 0 ? (
        <div className="sidebar-loader">Loading HCP profiles...</div>
      ) : hcps.length === 0 ? (
        <div className="sidebar-empty">
          <p>No HCPs found.</p>
          <p className="subtext">Click "Seed Demo Data" to populate profiles.</p>
        </div>
      ) : (
        <div className="hcp-list">
          {hcps.map((hcp) => {
            const isSelected = hcp.id === selectedHcpId;
            return (
              <div
                key={hcp.id}
                onClick={() => handleSelectHcp(hcp.id)}
                className={`hcp-item ${isSelected ? 'selected' : ''} sentiment-${hcp.recent_sentiment?.toLowerCase() || 'neutral'}`}
              >
                <div className="hcp-avatar">
                  <Stethoscope size={18} />
                </div>
                <div className="hcp-item-info">
                  <div className="hcp-item-row">
                    <span className="hcp-name">{hcp.name}</span>
                    {getSentimentIcon(hcp.recent_sentiment)}
                  </div>
                  <span className="hcp-spec">{hcp.specialty}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selectedHcp && (
        <div className="active-hcp-details">
          <h3>Active Profile</h3>
          <div className="detail-card glass-card">
            <h4>{selectedHcp.name}</h4>
            <span className="badge spec-badge">{selectedHcp.specialty}</span>
            
            <div className="detail-rows">
              {selectedHcp.clinic_name && (
                <div className="detail-row">
                  <Building2 size={14} />
                  <span>{selectedHcp.clinic_name}</span>
                </div>
              )}
              {selectedHcp.email && (
                <div className="detail-row">
                  <Mail size={14} />
                  <span className="truncate">{selectedHcp.email}</span>
                </div>
              )}
              {selectedHcp.phone && (
                <div className="detail-row">
                  <Phone size={14} />
                  <span>{selectedHcp.phone}</span>
                </div>
              )}
              {selectedHcp.address && (
                <div className="detail-row align-start">
                  <MapPin size={14} className="mt-xs" />
                  <span className="multiline">{selectedHcp.address}</span>
                </div>
              )}
            </div>
            
            <div className="sentiment-bar">
              <span className="lbl">Recent Sentiment:</span>
              <span className={`val sentiment-tag ${selectedHcp.recent_sentiment?.toLowerCase() || 'neutral'}`}>
                {selectedHcp.recent_sentiment || 'Neutral'}
              </span>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
