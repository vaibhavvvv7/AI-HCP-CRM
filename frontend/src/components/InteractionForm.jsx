import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { updateActiveFormState, logInteraction, resetActiveFormState } from '../store/crmSlice';
import { Calendar, Clock, Users, Phone } from 'lucide-react';

export default function InteractionForm() {
  const dispatch = useDispatch();
  const { activeFormState, selectedHcpId } = useSelector((state) => state.crm);

  const handleChange = (field, value) => {
    dispatch(updateActiveFormState({ [field]: value }));
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    
    const hcpId = selectedHcpId || 1;
    
    // Notes are required by the backend. Construct default if empty.
    const notesText = activeFormState.notes?.trim() || 
      `Discussed topics: ${activeFormState.topics || 'general scientific profiles'} with ${activeFormState.hcp_name || 'HCP'}. Outcomes: ${activeFormState.outcomes || 'none'}.`;

    // Construct ISO date string if date/time are provided
    let parsedDate = new Date();
    if (activeFormState.date) {
      const dateParts = activeFormState.date.split('-');
      if (dateParts.length === 3) {
        parsedDate.setFullYear(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2]));
      }
      if (activeFormState.time) {
        const timeParts = activeFormState.time.match(/(\d+):(\d+)\s*(AM|PM)/i);
        if (timeParts) {
          let hours = parseInt(timeParts[1]);
          const minutes = parseInt(timeParts[2]);
          const ampm = timeParts[3].toUpperCase();
          if (ampm === 'PM' && hours < 12) hours += 12;
          if (ampm === 'AM' && hours === 12) hours = 0;
          parsedDate.setHours(hours, minutes, 0, 0);
        }
      }
    }

    const payload = {
      hcp_id: hcpId,
      date: parsedDate.toISOString(),
      channel: activeFormState.interaction_type,
      notes: notesText,
      sentiment: activeFormState.sentiment,
      products_discussed: activeFormState.topics || 'None',
      doctor_rating: activeFormState.doctor_rating || null,
      feedback: activeFormState.feedback || null,
      summary: activeFormState.outcomes || null,
      next_steps: activeFormState.followup_actions || null
    };

    try {
      await dispatch(logInteraction(payload)).unwrap();
      dispatch(resetActiveFormState());
      alert('Interaction logged successfully!');
    } catch (err) {
      alert('Failed to log interaction: ' + err);
    }
  };

  const renderMaterials = () => {
    if (!activeFormState.materials_shared) return <span className="no-items">No materials shared.</span>;
    return activeFormState.materials_shared.split(',').map((item, idx) => (
      <span key={idx} className="form-tag material-tag">
        {item.trim()}
      </span>
    ));
  };

  const renderSamples = () => {
    if (!activeFormState.samples_distributed) return <span className="no-items">No samples added.</span>;
    return activeFormState.samples_distributed.split(',').map((item, idx) => (
      <span key={idx} className="form-tag sample-tag">
        {item.trim()}
      </span>
    ));
  };

  return (
    <form onSubmit={handleSubmit} className="interaction-form-container glass-card split-left-panel">
      <div className="form-main-header">
        <h2>Log HCP Interaction</h2>
      </div>

      <div className="form-section-group">
        <h3 className="section-title-label">Interaction Details</h3>
        
        <div className="form-grid-layout">
          <div className="form-input-field">
            <label>HCP Name</label>
            <input 
              type="text" 
              value={activeFormState.hcp_name} 
              onChange={(e) => handleChange('hcp_name', e.target.value)} 
              placeholder="Search or select HCP..."
            />
          </div>

          <div className="form-input-field">
            <label>Interaction Type</label>
            <select 
              value={activeFormState.interaction_type} 
              onChange={(e) => handleChange('interaction_type', e.target.value)}
            >
              <option value="Meeting">Meeting</option>
              <option value="Call">Call</option>
              <option value="Virtual">Virtual</option>
              <option value="Email">Email</option>
            </select>
          </div>

          <div className="form-input-field">
            <label>Date</label>
            <div className="relative-input-container">
              <Calendar className="field-icon" size={14} />
              <input 
                type="date" 
                value={activeFormState.date} 
                onChange={(e) => handleChange('date', e.target.value)} 
              />
            </div>
          </div>

          <div className="form-input-field">
            <label>Time</label>
            <div className="relative-input-container">
              <Clock className="field-icon" size={14} />
              <input 
                type="text" 
                value={activeFormState.time} 
                onChange={(e) => handleChange('time', e.target.value)} 
                placeholder="12:00 PM"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="form-section-group">
        <h3 className="section-title-label">Patient Details</h3>
        
        <div className="form-grid-layout">
          <div className="form-input-field">
            <label>Patient Name</label>
            <div className="relative-input-container">
              <Users className="field-icon" size={14} />
              <input 
                type="text" 
                value={activeFormState.attendees} 
                onChange={(e) => handleChange('attendees', e.target.value)} 
                placeholder="Enter patient name..."
              />
            </div>
          </div>

          <div className="form-input-field">
            <label>Patient Phone Number</label>
            <div className="relative-input-container">
              <Phone className="field-icon" size={14} />
              <input 
                type="text" 
                value={activeFormState.phone} 
                onChange={(e) => handleChange('phone', e.target.value)} 
                placeholder="555-0192"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="form-input-field full-width-field">
        <label>Topics Discussed</label>
        <textarea 
          value={activeFormState.topics} 
          onChange={(e) => handleChange('topics', e.target.value)} 
          placeholder="Enter key discussion points..."
          rows={2}
        />
      </div>

      <div className="form-section-group">
        <h3 className="section-title-label">Materials Shared / Samples Distributed</h3>
        
        <div className="shared-distributed-container">
          <div className="materials-shared-block">
            <label className="sub-label">Materials Shared</label>
            <div className="tags-display-row">
              {renderMaterials()}
              <button type="button" className="btn-search-add secondary-btn">
                <span>Search/Add</span>
              </button>
            </div>
          </div>

          <div className="samples-distributed-block">
            <label className="sub-label">Samples Distributed</label>
            <div className="tags-display-row">
              {renderSamples()}
              <button type="button" className="btn-search-add secondary-btn">
                <span>Add Sample</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="form-grid-layout">
        <div className="form-input-field">
          <label>Observed/Inferred HCP Sentiment</label>
          <div className="sentiment-radio-group">
            <label className={`sentiment-radio-label ${activeFormState.sentiment === 'Positive' ? 'selected-pos' : ''}`}>
              <input 
                type="radio" 
                name="sentiment" 
                value="Positive" 
                checked={activeFormState.sentiment === 'Positive'}
                onChange={() => handleChange('sentiment', 'Positive')}
              />
              <span className="dot pos-dot"></span>
              <span>Positive</span>
            </label>

            <label className={`sentiment-radio-label ${activeFormState.sentiment === 'Neutral' ? 'selected-neu' : ''}`}>
              <input 
                type="radio" 
                name="sentiment" 
                value="Neutral" 
                checked={activeFormState.sentiment === 'Neutral'}
                onChange={() => handleChange('sentiment', 'Neutral')}
              />
              <span className="dot neu-dot"></span>
              <span>Neutral</span>
            </label>

            <label className={`sentiment-radio-label ${activeFormState.sentiment === 'Negative' ? 'selected-neg' : ''}`}>
              <input 
                type="radio" 
                name="sentiment" 
                value="Negative" 
                checked={activeFormState.sentiment === 'Negative'}
                onChange={() => handleChange('sentiment', 'Negative')}
              />
              <span className="dot neg-dot"></span>
              <span>Negative</span>
            </label>
          </div>
        </div>

        <div className="form-input-field">
          <label>Doctor Rating (1-5 Scale)</label>
          <div className="rating-selector-buttons">
            {[1, 2, 3, 4, 5].map((num) => (
              <button
                type="button"
                key={num}
                onClick={() => handleChange('doctor_rating', num)}
                className={`btn-rating-num ${activeFormState.doctor_rating === num ? 'active-rating' : ''}`}
              >
                {num}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="form-input-field full-width-field">
        <label>Outcomes</label>
        <textarea 
          value={activeFormState.outcomes} 
          onChange={(e) => handleChange('outcomes', e.target.value)} 
          placeholder="Key outcomes or agreements..."
          rows={2}
        />
      </div>

      <div className="form-input-field full-width-field">
        <label>Suggestions / Feedback</label>
        <textarea 
          value={activeFormState.feedback} 
          onChange={(e) => handleChange('feedback', e.target.value)} 
          placeholder="Any additional suggestions or feedback from the doctor..."
          rows={2}
        />
      </div>

      <div className="form-input-field full-width-field">
        <label>Follow-up Actions</label>
        <textarea 
          value={activeFormState.followup_actions} 
          onChange={(e) => handleChange('followup_actions', e.target.value)} 
          placeholder="Follow-up Actions..."
          rows={2}
        />
      </div>

      <div className="form-input-field full-width-field">
        <label>Discussion Notes</label>
        <textarea 
          value={activeFormState.notes || ''} 
          onChange={(e) => handleChange('notes', e.target.value)} 
          placeholder="Enter detailed notes or meeting transcript..."
          rows={3}
          required
        />
      </div>

      <div className="form-actions" style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-start' }}>
        <button 
          type="submit" 
          className="primary-btn btn-submit"
        >
          Log Interaction
        </button>
      </div>
    </form>
  );
}
