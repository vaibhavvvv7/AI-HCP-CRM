import React, { useState } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { scheduleTask, toggleTaskStatus } from '../store/crmSlice';
import { CheckSquare, Square, Calendar, Plus, Clock, ClipboardList } from 'lucide-react';

export default function FollowUpTasks() {
  const dispatch = useDispatch();
  const { tasks, selectedHcpId } = useSelector((state) => state.crm);

  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState(new Date().toISOString().split('T')[0]);
  const [submitting, setSubmitting] = useState(false);

  const handleToggle = async (taskId, currentStatus) => {
    const newStatus = currentStatus === 'Pending' ? 'Completed' : 'Pending';
    try {
      await dispatch(toggleTaskStatus({ taskId, status: newStatus, hcpId: selectedHcpId })).unwrap();
    } catch (err) {
      alert('Error updating task: ' + err);
    }
  };

  const handleAddTask = async (e) => {
    e.preventDefault();
    if (!description.trim() || !selectedHcpId) return;

    setSubmitting(true);
    const payload = {
      hcp_id: selectedHcpId,
      description,
      due_date: dueDate,
      status: 'Pending'
    };

    try {
      await dispatch(scheduleTask(payload)).unwrap();
      setDescription('');
    } catch (err) {
      alert('Failed to schedule task: ' + err);
    } finally {
      setSubmitting(false);
    }
  };

  const pendingTasks = tasks.filter(t => t.status === 'Pending');
  const completedTasks = tasks.filter(t => t.status === 'Completed');

  return (
    <div className="tasks-container glass-card">
      <div className="tasks-header">
        <h3>Follow-Up Scheduler</h3>
        <p className="subtext">Track action items and pending deliverables</p>
      </div>

      <form onSubmit={handleAddTask} className="quick-task-form">
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="New action item (e.g. 'Email trial brochures')"
          required
        />
        <div className="due-input-container">
          <Calendar size={14} className="due-icon" />
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            required
          />
        </div>
        <button type="submit" disabled={submitting || !description.trim()} className="btn-add-task primary-btn">
          <Plus size={14} />
          <span>{submitting ? 'Adding...' : 'Add'}</span>
        </button>
      </form>

      <div className="tasks-board">
        <div className="tasks-column">
          <h4>
            <span>Pending Action Items</span>
            <span className="task-count">{pendingTasks.length}</span>
          </h4>
          <div className="tasks-list">
            {pendingTasks.map(task => (
              <div key={task.id} className="task-card pending">
                <button onClick={() => handleToggle(task.id, task.status)} className="task-checkbox-btn">
                  <Square size={16} />
                </button>
                <div className="task-info">
                  <span className="task-desc">{task.description}</span>
                  <div className="task-meta">
                    <Clock size={12} />
                    <span>Due: {new Date(task.due_date).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
            ))}
            {pendingTasks.length === 0 && (
              <div className="task-list-empty">
                <ClipboardList size={24} />
                <p>All caught up!</p>
              </div>
            )}
          </div>
        </div>

        <div className="tasks-column">
          <h4>
            <span>Completed Deliverables</span>
            <span className="task-count">{completedTasks.length}</span>
          </h4>
          <div className="tasks-list">
            {completedTasks.map(task => (
              <div key={task.id} className="task-card completed">
                <button onClick={() => handleToggle(task.id, task.status)} className="task-checkbox-btn checked">
                  <CheckSquare size={16} />
                </button>
                <div className="task-info">
                  <span className="task-desc">{task.description}</span>
                  <div className="task-meta">
                    <span>Completed</span>
                  </div>
                </div>
              </div>
            ))}
            {completedTasks.length === 0 && (
              <div className="task-list-empty">
                <p className="subtext">No completed tasks yet.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
