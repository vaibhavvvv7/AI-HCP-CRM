import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

const API_BASE = 'http://127.0.0.1:8000/api';

// --- Async Thunks ---

export const seedDatabase = createAsyncThunk(
  'crm/seedDatabase',
  async (_, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/seed`, { method: 'POST' });
      const data = await response.json();
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchHcps = createAsyncThunk(
  'crm/fetchHcps',
  async (_, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/hcps`);
      if (!response.ok) throw new Error('Failed to fetch HCPs');
      return await response.json();
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchProducts = createAsyncThunk(
  'crm/fetchProducts',
  async (_, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/products`);
      if (!response.ok) throw new Error('Failed to fetch products');
      return await response.json();
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchInteractions = createAsyncThunk(
  'crm/fetchInteractions',
  async (hcpId, { rejectWithValue }) => {
    try {
      const url = hcpId ? `${API_BASE}/interactions?hcp_id=${hcpId}` : `${API_BASE}/interactions`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch interactions');
      return await response.json();
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchTasks = createAsyncThunk(
  'crm/fetchTasks',
  async (hcpId, { rejectWithValue }) => {
    try {
      const url = hcpId ? `${API_BASE}/tasks?hcp_id=${hcpId}` : `${API_BASE}/tasks`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch tasks');
      return await response.json();
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const logInteraction = createAsyncThunk(
  'crm/logInteraction',
  async (payload, { dispatch, rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/interactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error('Failed to log interaction');
      const data = await response.json();
      // Refresh interactions and HCP list (to update sentiments)
      dispatch(fetchInteractions(payload.hcp_id));
      dispatch(fetchHcps());
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const editInteraction = createAsyncThunk(
  'crm/editInteraction',
  async ({ interactionId, payload, hcpId }, { dispatch, rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/interactions/${interactionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error('Failed to update interaction');
      const data = await response.json();
      dispatch(fetchInteractions(hcpId));
      dispatch(fetchHcps());
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const scheduleTask = createAsyncThunk(
  'crm/scheduleTask',
  async (payload, { dispatch, rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error('Failed to schedule task');
      const data = await response.json();
      dispatch(fetchTasks(payload.hcp_id));
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const toggleTaskStatus = createAsyncThunk(
  'crm/toggleTaskStatus',
  async ({ taskId, status, hcpId }, { dispatch, rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/tasks/${taskId}?status=${status}`, {
        method: 'PUT',
      });
      if (!response.ok) throw new Error('Failed to update task');
      const data = await response.json();
      dispatch(fetchTasks(hcpId));
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const sendMessageToAgent = createAsyncThunk(
  'crm/sendMessageToAgent',
  async ({ message, hcpId, chatHistory }, { dispatch, rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          hcp_id: hcpId,
          chat_history: chatHistory.map(m => ({ role: m.role, content: m.content }))
        }),
      });
      if (!response.ok) throw new Error('AI Agent error');
      const data = await response.json();
      
      // If the response contains suggested tools/actions, trigger store updates
      if (data.suggested_actions && data.suggested_actions.length > 0) {
        data.suggested_actions.forEach(action => {
          if (action.type === 'log_interaction' || action.type === 'edit_interaction') {
            dispatch(fetchInteractions(hcpId));
            dispatch(fetchHcps());
          } else if (action.type === 'schedule_followup') {
            dispatch(fetchTasks(hcpId));
          }
        });
      }
      
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

// --- CRM Slice ---

const crmSlice = createSlice({
  name: 'crm',
  initialState: {
    hcps: [],
    selectedHcpId: null,
    interactions: [],
    tasks: [],
    products: [],
    chatHistory: [],
    emailDraft: null,
    loading: false,
    agentTyping: false,
    error: null,
    activeTab: 'chat', // 'chat' | 'form'
    activeFormState: {
      hcp_name: '',
      phone: '',
      interaction_type: 'Meeting',
      date: new Date().toISOString().split('T')[0],
      time: '07:36 PM',
      attendees: '',
      topics: '',
      materials_shared: '',
      samples_distributed: '',
      sentiment: 'Neutral',
      outcomes: '',
      followup_actions: '',
      doctor_rating: 0,
      feedback: '',
      notes: ''
    }
  },
  reducers: {
    selectHcp: (state, action) => {
      state.selectedHcpId = action.payload;
      state.chatHistory = []; // Reset chat history for new doctor
      state.emailDraft = null;
    },
    setActiveTab: (state, action) => {
      state.activeTab = action.payload;
    },
    clearEmailDraft: (state) => {
      state.emailDraft = null;
    },
    addLocalUserMessage: (state, action) => {
      state.chatHistory.push({ role: 'user', content: action.payload });
    },
    updateActiveFormState: (state, action) => {
      state.activeFormState = {
        ...state.activeFormState,
        ...action.payload
      };
    },
    resetActiveFormState: (state) => {
      state.activeFormState = {
        hcp_name: '',
        phone: '',
        interaction_type: 'Meeting',
        date: new Date().toISOString().split('T')[0],
        time: '07:36 PM',
        attendees: '',
        topics: '',
        materials_shared: '',
        samples_distributed: '',
        sentiment: 'Neutral',
        outcomes: '',
        followup_actions: '',
        doctor_rating: 0,
        feedback: '',
        notes: ''
      };
    }
  },
  extraReducers: (builder) => {
    // Seeding
    builder.addCase(seedDatabase.fulfilled, (state) => {
      state.error = null;
    });
    
    // Fetch HCPs
    builder.addCase(fetchHcps.pending, (state) => {
      state.loading = true;
    });
    builder.addCase(fetchHcps.fulfilled, (state, action) => {
      state.loading = false;
      state.hcps = action.payload;
      if (!state.selectedHcpId && action.payload.length > 0) {
        state.selectedHcpId = action.payload[0].id;
      }
    });
    builder.addCase(fetchHcps.rejected, (state, action) => {
      state.loading = false;
      state.error = action.payload;
    });

    // Fetch Products
    builder.addCase(fetchProducts.fulfilled, (state, action) => {
      state.products = action.payload;
    });

    // Fetch Interactions
    builder.addCase(fetchInteractions.fulfilled, (state, action) => {
      state.interactions = action.payload;
    });

    // Fetch Tasks
    builder.addCase(fetchTasks.fulfilled, (state, action) => {
      state.tasks = action.payload;
    });

    // AI Agent Sending
    builder.addCase(sendMessageToAgent.pending, (state) => {
      state.agentTyping = true;
    });
    builder.addCase(sendMessageToAgent.fulfilled, (state, action) => {
      state.agentTyping = false;
      const { response, suggested_actions } = action.payload;
      state.chatHistory.push({ role: 'assistant', content: response });
      
      // Update form state if agent triggered a log_interaction or edit_interaction!
      if (suggested_actions && suggested_actions.length > 0) {
        suggested_actions.forEach(actionItem => {
          if ((actionItem.type === 'log_interaction' || actionItem.type === 'edit_interaction') && actionItem.data) {
            const data = actionItem.data;
            state.activeFormState = {
              hcp_name: data.hcp_name !== undefined ? data.hcp_name : state.activeFormState.hcp_name,
              phone: data.phone !== undefined ? data.phone : state.activeFormState.phone,
              interaction_type: data.interaction_type !== undefined ? data.interaction_type : state.activeFormState.interaction_type,
              date: data.date !== undefined ? data.date : state.activeFormState.date,
              time: data.time !== undefined ? data.time : state.activeFormState.time,
              attendees: data.attendees !== undefined ? data.attendees : state.activeFormState.attendees,
              topics: data.topics !== undefined ? data.topics : state.activeFormState.topics,
              materials_shared: data.materials_shared !== undefined ? data.materials_shared : state.activeFormState.materials_shared,
              samples_distributed: data.samples_distributed !== undefined ? data.samples_distributed : state.activeFormState.samples_distributed,
              sentiment: data.sentiment !== undefined ? data.sentiment : state.activeFormState.sentiment,
              outcomes: data.outcomes !== undefined ? data.outcomes : state.activeFormState.outcomes,
              followup_actions: data.followup_actions !== undefined ? data.followup_actions : state.activeFormState.followup_actions,
              doctor_rating: data.doctor_rating !== undefined ? data.doctor_rating : state.activeFormState.doctor_rating,
              feedback: data.feedback !== undefined ? data.feedback : state.activeFormState.feedback,
              notes: data.notes !== undefined ? data.notes : state.activeFormState.notes,
            };
          }
        });

        // Look for generated email draft in actions
        const emailAction = suggested_actions.find(a => a.type === 'generate_followup_email');
        if (emailAction && emailAction.data && emailAction.data.status === 'success') {
          state.emailDraft = emailAction.data;
        }
      }
    });
    builder.addCase(sendMessageToAgent.rejected, (state, action) => {
      state.agentTyping = false;
      state.chatHistory.push({
        role: 'assistant',
        content: `Error contacting agent: ${action.payload || 'Unknown error'}. Please verify backend is running.`
      });
    });
  }
});

export const { selectHcp, setActiveTab, clearEmailDraft, addLocalUserMessage, updateActiveFormState, resetActiveFormState } = crmSlice.actions;
export default crmSlice.reducer;
