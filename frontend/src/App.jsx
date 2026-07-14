import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchHcps, fetchProducts, fetchInteractions, fetchTasks, setActiveTab } from './store/crmSlice';
import HcpSelector from './components/HcpSelector';
import ChatInterface from './components/ChatInterface';
import InteractionForm from './components/InteractionForm';
import HistoryView from './components/HistoryView';
import FollowUpTasks from './components/FollowUpTasks';
import { Activity, MessageSquare, ListTodo, Sparkles } from 'lucide-react';

export default function App() {
  const dispatch = useDispatch();
  const { selectedHcpId, activeTab } = useSelector((state) => state.crm);

  // 1. Initial Load: Fetch HCP list and products
  useEffect(() => {
    dispatch(fetchHcps());
    dispatch(fetchProducts());
  }, [dispatch]);

  // 2. Secondary Load: Fetch items for selected doctor
  useEffect(() => {
    if (selectedHcpId) {
      dispatch(fetchInteractions(selectedHcpId));
      dispatch(fetchTasks(selectedHcpId));
    }
  }, [selectedHcpId, dispatch]);

  // 3. Ambient Mouse Coordinates Spotlight Effect
  useEffect(() => {
    const handleMouseMove = (e) => {
      document.documentElement.style.setProperty('--mouse-x', `${e.clientX}px`);
      document.documentElement.style.setProperty('--mouse-y', `${e.clientY}px`);
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <>
      {/* Floating Ambient Mesh Orbs */}
      <div className="ambient-orb orb-1"></div>
      <div className="ambient-orb orb-2"></div>

      <div className="app-container">
        {/* App Header */}
        <header className="app-header glass-panel">
          <div className="brand-section">
            <div className="brand-logo">
              <Activity size={18} />
            </div>
            <h1 className="app-title">Aivoa AI CRM</h1>
          </div>
          <div className="user-status-widget">
            <div className="status-dot"></div>
            <span className="status-text">AI Interaction Logger</span>
          </div>
        </header>

        {/* Main Grid Workspace */}
        <main className="dashboard-grid split-screen-layout">
          {/* Left Panel: Log HCP Interaction Form */}
          <InteractionForm />

          {/* Right Panel: AI Assistant Chat */}
          <ChatInterface />
        </main>
      </div>
    </>
  );
}
