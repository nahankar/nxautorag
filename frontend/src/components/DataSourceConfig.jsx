import React, { useState, useEffect } from 'react';
import axios from 'axios';

const DataSourceConfig = () => {
  // Data source state
  const [sourceType, setSourceType] = useState('file');
  const [mysqlConfig, setMysqlConfig] = useState({
    type: 'mysql',
    host: '',
    port: 3306,
    user: '',
    password: '',
    database: ''
  });
  const [urlConfig, setUrlConfig] = useState({
    type: 'url',
    url: ''
  });
  const [files, setFiles] = useState([]);

  // LLM config state
  const [llmConfig, setLlmConfig] = useState({
    llm_provider: 'local',
    llm_model: 'mistralai/Mixtral-8x7B-Instruct-v0.1',
    api_token: '',
    azure_endpoint: '',
    azure_deployment: '',
    api_version: '2023-12-01-preview'
  });

  // Google config state
  const [googleConfig, setGoogleConfig] = useState({
    type: 'google',
    services: [],
    max_items: 50
  });

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [showApiToken, setShowApiToken] = useState(false);
  const [showDbPassword, setShowDbPassword] = useState(false);
  const [latestConfig, setLatestConfig] = useState(null);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isLoadingGoogleAuth, setIsLoadingGoogleAuth] = useState(false);
  const [googleAuthStatus, setGoogleAuthStatus] = useState(null);
  const [isIngestingGoogle, setIsIngestingGoogle] = useState(false);

  // Load latest configuration on mount and when sourceType changes
  useEffect(() => {
    fetchLatestConfig();
  }, [sourceType]);

  // Check Google auth status when Google tab is selected
  useEffect(() => {
    if (sourceType === 'google') {
      checkGoogleAuthStatus();
    }
  }, [sourceType]);

  // Check URL parameters for auth callback
  useEffect(() => {
    // Check if the URL has auth=success or auth=error
    const urlParams = new URLSearchParams(window.location.search);
    const authStatus = urlParams.get('auth');
    
    if (authStatus === 'success') {
      // Clear the URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);
      // Check auth status after successful login
      checkGoogleAuthStatus();
      setMessage('Successfully authenticated with Google');
      // Set source type to Google after successful authentication
      setSourceType('google');
    } else if (authStatus === 'error') {
      // Clear the URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);
      const errorMessage = urlParams.get('message') || 'Authentication failed';
      setError(`Google authentication error: ${errorMessage}`);
    }
  }, []);

  // Fetch the latest configuration from the server
  const fetchLatestConfig = async () => {
    setIsLoadingConfig(true);
    try {
      const response = await axios.get('http://localhost:8000/get-latest-config');
      if (response.data) {
        setLatestConfig(response.data);
        
        // If we have matching config for the current tab, pre-populate the form
        if (sourceType === 'llm' && response.data.llm_config) {
          setLlmConfig(response.data.llm_config);
        } else if (sourceType === 'mysql' && response.data.mysql_config) {
          setMysqlConfig(response.data.mysql_config);
        } else if (sourceType === 'url' && response.data.url_config) {
          setUrlConfig(response.data.url_config);
        }
      }
    } catch (err) {
      console.error('Failed to fetch latest config:', err);
    } finally {
      setIsLoadingConfig(false);
    }
  };

  // Fetch Google authentication status
  const checkGoogleAuthStatus = async () => {
    setIsLoadingGoogleAuth(true);
    try {
      const response = await axios.get('http://localhost:8000/google/auth-status');
      setGoogleAuthStatus(response.data);
    } catch (err) {
      console.error('Failed to check Google auth status:', err);
      setGoogleAuthStatus({
        is_authenticated: false,
        message: 'Error checking authentication status'
      });
    } finally {
      setIsLoadingGoogleAuth(false);
    }
  };

  // Handle form input changes
  const handleMysqlChange = (e) => {
    const { name, value } = e.target;
    setMysqlConfig({ ...mysqlConfig, [name]: name === 'port' ? parseInt(value) : value });
  };

  const handleUrlChange = (e) => {
    setUrlConfig({ ...urlConfig, url: e.target.value });
  };

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files).slice(0, 5)); // Limit to max 5 files
  };

  const handleLlmChange = (e) => {
    const { name, value } = e.target;
    
    if (name === 'llm_provider') {
      // When provider changes to Azure, update model to match deployment
      if (value === 'azure') {
        setLlmConfig({
          ...llmConfig,
          llm_provider: value,
          llm_model: llmConfig.azure_deployment || 'gpt-4o'  // Use deployment name or default
        });
      } else {
        // For other providers, keep the current model or set a default
        setLlmConfig({
          ...llmConfig,
          llm_provider: value
        });
      }
    } else if (name === 'azure_deployment' && llmConfig.llm_provider === 'azure') {
      // When Azure deployment changes, update model to match
      setLlmConfig({
        ...llmConfig,
        azure_deployment: value,
        llm_model: value  // Keep model in sync with deployment for Azure
      });
    } else {
      // Normal case for other field changes
    setLlmConfig({ ...llmConfig, [name]: value });
    }
  };

  const handleGoogleChange = (e) => {
    const { name, value } = e.target;
    setGoogleConfig({ ...googleConfig, [name]: value });
  };

  // Toggle password/token visibility
  const toggleApiTokenVisibility = () => {
    setShowApiToken(!showApiToken);
  };

  const toggleDbPasswordVisibility = () => {
    setShowDbPassword(!showDbPassword);
  };

  // Format the latest config for display
  const formatConfigDisplay = (config) => {
    if (!config) return "No configuration found";
    return JSON.stringify(config, null, 2);
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage('');
    setError('');

    try {
      // Create form data
      const formData = new FormData();
      
      // Create configuration object
      const configData = {
        sourceType,
        llm_config: llmConfig,
        ...(sourceType === 'mysql' ? { mysql_config: mysqlConfig } : {}),
        ...(sourceType === 'url' ? { url_config: urlConfig } : {}),
        ...(sourceType === 'google' ? { google_config: googleConfig } : {})
      };
      
      // Add configuration to form data
      formData.append('config', JSON.stringify(configData));
      
      // Handle file uploads
      if (sourceType === 'file') {
        for (const file of files) {
          formData.append('files', file);
        }
        // Also add file metadata to config
        formData.append('file_metadata', JSON.stringify(Array.from(files).map(f => ({
          name: f.name,
          type: f.type,
          size: f.size,
          lastModified: f.lastModified
        }))));
      }
      
      // Submit data
      const response = await axios.post('http://localhost:8000/ingest', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      if (response.data.status === 'Ingestion Successful') {
        setMessage(`Configuration saved and data ingested successfully ✅ ${response.data.files_stored ? `(${response.data.files_stored} files stored)` : ''}`);
        // Refresh latest config after saving
        fetchLatestConfig();
      } else if (response.data.status === 'Config saved') {
        setMessage('Configuration saved successfully ✅');
        // Refresh latest config after saving
        fetchLatestConfig();
      } else {
        setError(response.data.message || 'An error occurred');
      }
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setIsLoadingGoogleAuth(true);
    try {
      // Get the login URL
      const response = await axios.get('http://localhost:8000/google/login');
      if (response.data && response.data.auth_url) {
        // Redirect to Google's authorization page
        window.location.href = response.data.auth_url;
      } else {
        setError('Failed to get Google authorization URL');
      }
    } catch (err) {
      console.error('Failed to initiate Google login:', err);
      setError(err.response?.data?.detail || 'Error initiating Google login');
    } finally {
      setIsLoadingGoogleAuth(false);
    }
  };

  const handleGoogleLogout = async () => {
    setIsLoadingGoogleAuth(true);
    try {
      await axios.post('http://localhost:8000/google/logout');
      setGoogleAuthStatus({
        is_authenticated: false,
        message: 'Logged out from Google'
      });
      // Reset Google services selection but keep the type
      setGoogleConfig({
        ...googleConfig,
        type: 'google',
        services: []
      });
    } catch (err) {
      console.error('Failed to logout from Google:', err);
      setError(err.response?.data?.detail || 'Error logging out from Google');
    } finally {
      setIsLoadingGoogleAuth(false);
    }
  };

  const ingestGoogleData = async () => {
    if (!googleAuthStatus || !googleAuthStatus.is_authenticated || !latestConfig) {
      setError('Google authentication or configuration required before ingestion');
      return;
    }

    setIsIngestingGoogle(true);
    setError('');
    setMessage('');
    try {
      const response = await axios.post('http://localhost:8000/google/ingest', {
        services: googleConfig.services,
        max_items: googleConfig.max_items
      });
      
      if (response.data.status === 'success') {
        setMessage(`Google data ingested successfully! ${response.data.items_count || ''} items processed.`);
      } else {
        setError('Error ingesting Google data: ' + (response.data.message || 'Unknown error'));
      }
    } catch (err) {
      console.error('Failed to ingest Google data:', err);
      setError(err.response?.data?.detail || 'Error ingesting Google data');
    } finally {
      setIsIngestingGoogle(false);
    }
  };

  const handleTestGoogleConnection = async () => {
    setIsLoadingGoogleAuth(true);
    try {
      const response = await axios.post('http://localhost:8000/google/test-connection');
      if (response.data.status === 'success') {
        setMessage(`Connected to Google successfully. Found ${response.data.file_count} Drive files.`);
      } else {
        setError(response.data.message || 'Error testing Google connection');
      }
    } catch (err) {
      console.error('Failed to test Google connection:', err);
      setError(err.response?.data?.detail || 'Error testing Google connection');
    } finally {
      setIsLoadingGoogleAuth(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
      <h2 className="text-2xl font-bold mb-6">Data Source Configuration</h2>
      
        <div className="mb-6">
          <div className="bg-gray-100 rounded-lg p-1 flex space-x-1">
            <button
              onClick={() => setSourceType('file')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium ${
                sourceType === 'file' ? 'bg-white shadow-sm' : 'hover:bg-gray-200'
              }`}
            >
              <span className="flex items-center justify-center">
                <i className="fas fa-file mr-2"></i> File Upload
              </span>
            </button>
            
            <button
              onClick={() => setSourceType('mysql')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium ${
                sourceType === 'mysql' ? 'bg-white shadow-sm' : 'hover:bg-gray-200'
              }`}
            >
              <span className="flex items-center justify-center">
                <i className="fas fa-database mr-2"></i> Database
              </span>
            </button>
            
            <button
              onClick={() => setSourceType('url')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium ${
                sourceType === 'url' ? 'bg-white shadow-sm' : 'hover:bg-gray-200'
              }`}
            >
              <span className="flex items-center justify-center">
                <i className="fas fa-globe mr-2"></i> Web URL
              </span>
            </button>
            
            <button
              onClick={() => setSourceType('llm')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium ${
                sourceType === 'llm' ? 'bg-white shadow-sm' : 'hover:bg-gray-200'
              }`}
            >
              <span className="flex items-center justify-center">
                <i className="fas fa-robot mr-2"></i> LLM Config
              </span>
            </button>
            
            <button
              onClick={() => setSourceType('google')}
              className={`flex-1 py-2 px-4 rounded-md text-sm font-medium ${
                sourceType === 'google' ? 'bg-white shadow-sm' : 'hover:bg-gray-200'
              }`}
            >
              <span className="flex items-center justify-center">
                <i className="fab fa-google mr-2"></i> Google
              </span>
            </button>
          </div>
          
          <form onSubmit={handleSubmit}>
            {/* File Upload Form */}
            {sourceType === 'file' && (
              <div className="mb-8">
                <h3 className="font-medium mb-3">Upload Files (PDF, DOCX, TXT):</h3>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.docx,.txt"
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                    required={sourceType === 'file'}
                  />
                  <label
                    htmlFor="file-upload"
                    className="cursor-pointer inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    Choose files
                  </label>
                  <p className="text-sm text-gray-500 mt-2">Maximum 5 files</p>
                  
                  {files.length > 0 && (
                    <div className="mt-4 text-left">
                      <p className="font-medium">Selected files:</p>
                      <ul className="list-disc pl-5 mt-2">
                        {Array.from(files).map((file, index) => (
                          <li key={index} className="text-sm text-gray-700">{file.name}</li>
                        ))}
                      </ul>
                    </div>
                  )}
          </div>
        </div>
            )}
        
        {/* MySQL Form */}
        {sourceType === 'mysql' && (
              <div className="mb-8">
                <h3 className="font-medium mb-3">MySQL Connection:</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Host:</label>
                <input
                  type="text"
                  name="host"
                  value={mysqlConfig.host}
                  onChange={handleMysqlChange}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
              <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Port:</label>
                <input
                  type="number"
                  name="port"
                  value={mysqlConfig.port}
                  onChange={handleMysqlChange}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
              <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">User:</label>
                <input
                  type="text"
                  name="user"
                  value={mysqlConfig.user}
                  onChange={handleMysqlChange}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
              <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Password:</label>
                    <div className="relative">
                <input
                        type={showDbPassword ? "text" : "password"}
                  name="password"
                  value={mysqlConfig.password}
                  onChange={handleMysqlChange}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  required
                />
                      <button 
                        type="button" 
                        className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 cursor-pointer"
                        onClick={toggleDbPasswordVisibility}
                      >
                        {showDbPassword ? (
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7A9.97 9.97 0 014.02 8.971m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                          </svg>
                        ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        )}
                      </button>
                    </div>
              </div>
              <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Database:</label>
                <input
                  type="text"
                  name="database"
                  value={mysqlConfig.database}
                  onChange={handleMysqlChange}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>
            </div>

                {/* Current Database Configuration */}
                {latestConfig && latestConfig.mysql_config && (
                  <div className="mt-6 p-4 bg-gray-50 rounded-md border border-gray-200">
                    <h4 className="font-medium text-sm mb-2">Current Database Configuration:</h4>
                    <pre className="text-xs bg-white p-3 rounded overflow-auto max-h-40">
                      {JSON.stringify({
                        host: latestConfig.mysql_config.host,
                        port: latestConfig.mysql_config.port,
                        user: latestConfig.mysql_config.user,
                        database: latestConfig.mysql_config.database,
                        // Don't show password
                        password: "********"
                      }, null, 2)}
                    </pre>
                </div>
              )}
          </div>
        )}
        
        {/* URL Form */}
        {sourceType === 'url' && (
              <div className="mb-8">
                <h3 className="font-medium mb-3">Web URL:</h3>
            <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Enter URL:</label>
              <input
                type="url"
                value={urlConfig.url}
                onChange={handleUrlChange}
                placeholder="https://example.com"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                required={sourceType === 'url'}
              />
            </div>
          </div>
        )}
        
        {/* LLM Configuration */}
            {sourceType === 'llm' && (
              <div className="mb-8">
                <h3 className="font-medium mb-3">LLM Configuration:</h3>
          <div className="space-y-4">
            <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">LLM Provider:</label>
              <select
                name="llm_provider"
                value={llmConfig.llm_provider}
                onChange={handleLlmChange}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="local">Local Hosted (Free)</option>
                <option value="hf_free">HuggingFace Free Tier (Rate-Limited)</option>
                <option value="hf_paid">HuggingFace Paid API</option>
                <option value="azure">Azure OpenAI Paid API</option>
              </select>
            </div>
            
            <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Model:</label>
              <select
                name="llm_model"
                value={llmConfig.llm_model}
                onChange={handleLlmChange}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                {(llmConfig.llm_provider === 'local' || llmConfig.llm_provider.startsWith('hf_')) && (
                  <>
                    <option value="mistralai/Mixtral-8x7B-Instruct-v0.1">Mistralai/Mixtral-8x7B-Instruct-v0.1</option>
                    <option value="tiiuae/falcon-7b-instruct">Tiiuae/Falcon-7B-Instruct</option>
                    <option value="meta-llama/Meta-LLaMA-3-8B">Meta-LLaMA-3-8B</option>
                          <option value="google/flan-t5-base">Google/Flan-T5-Base (Non-gated)</option>
                          <option value="Xenova/distilbert-base-uncased">Xenova/DistilBERT (Embedded)</option>
                    <option value="custom">Custom HuggingFace</option>
                  </>
                )}
                
                {llmConfig.llm_provider === 'azure' && (
                  <>
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="gpt-4o-mini">GPT-4o mini</option>
                    <option value="gpt-4-turbo">GPT-4 Turbo</option>
                    <option value="gpt-3.5-turbo">GPT-3.5-Turbo</option>
                  </>
                )}
              </select>
            </div>
            
            {llmConfig.llm_model === 'custom' && (
              <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Custom Model ID:</label>
                <input
                  type="text"
                  name="llm_model"
                  onChange={handleLlmChange}
                  placeholder="e.g., google/flan-t5-xxl"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            )}
            
            {llmConfig.llm_provider.startsWith('hf_') && (
              <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                  HuggingFace API Token:
                  {llmConfig.llm_provider === 'hf_free' ? ' (Optional)' : ' (Required)'}
                </label>
                      <div className="relative">
                <input
                          type={showApiToken ? "text" : "password"}
                  name="api_token"
                  value={llmConfig.api_token}
                  onChange={handleLlmChange}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  required={llmConfig.llm_provider === 'hf_paid'}
                />
                        <button 
                          type="button" 
                          className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 cursor-pointer"
                          onClick={toggleApiTokenVisibility}
                        >
                          {showApiToken ? (
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7A9.97 9.97 0 014.02 8.971m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                            </svg>
                          ) : (
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                          )}
                        </button>
                      </div>
              </div>
            )}
            
            {llmConfig.llm_provider === 'azure' && (
              <>
                      <div className="mb-4">
                        <label htmlFor="api_token" className="block text-sm font-medium text-gray-700 mb-1">
                          Azure OpenAI API Key:
                        </label>
                        <div className="relative">
                  <input
                            type={showApiToken ? "text" : "password"}
                            id="api_token"
                    name="api_token"
                    value={llmConfig.api_token}
                    onChange={handleLlmChange}
                            placeholder="Enter your Azure OpenAI API key"
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                          />
                          <button
                            type="button"
                            onClick={toggleApiTokenVisibility}
                            className="absolute inset-y-0 right-0 pr-3 flex items-center"
                          >
                            <i className={`fas ${showApiToken ? 'fa-eye-slash' : 'fa-eye'} text-gray-400`}></i>
                          </button>
                        </div>
                </div>
                      <div className="mb-4">
                        <label htmlFor="azure_endpoint" className="block text-sm font-medium text-gray-700 mb-1">
                          Azure OpenAI Endpoint:
                        </label>
                  <input
                    type="text"
                          id="azure_endpoint"
                    name="azure_endpoint"
                    value={llmConfig.azure_endpoint}
                    onChange={handleLlmChange}
                          placeholder="https://your-resource-name.openai.azure.com/"
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                  />
                </div>
                      <div className="mb-4">
                        <label htmlFor="azure_deployment" className="block text-sm font-medium text-gray-700 mb-1">
                          Azure OpenAI Deployment Name:
                        </label>
                  <input
                    type="text"
                          id="azure_deployment"
                    name="azure_deployment"
                    value={llmConfig.azure_deployment}
                    onChange={handleLlmChange}
                          placeholder="Enter your deployment name (e.g. gpt4)"
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                        />
                      </div>
                      <div className="mb-4">
                        <label htmlFor="api_version" className="block text-sm font-medium text-gray-700 mb-1">
                          Azure OpenAI API Version:
                        </label>
                        <input
                          type="text"
                          id="api_version"
                          name="api_version"
                          value={llmConfig.api_version || "2023-05-15"}
                          onChange={handleLlmChange}
                          placeholder="2023-05-15"
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2 border"
                        />
                        <p className="mt-1 text-sm text-gray-500">
                          Common values: 2023-05-15, 2023-12-01-preview, or 2024-02-15-preview
                        </p>
                      </div>
                    </>
                  )}
                  
                  <p className="text-sm text-gray-600 mt-2">
                    Note: Local Hosted is free; HuggingFace Free Tier is rate-limited; Paid options require subscription.
                  </p>

                  {/* Current LLM Configuration */}
                  {latestConfig && latestConfig.llm_config && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-md border border-gray-200">
                      <h4 className="font-medium text-sm mb-2">Current LLM Configuration:</h4>
                      <pre className="text-xs bg-white p-3 rounded overflow-auto max-h-40">
                        {JSON.stringify({
                          llm_provider: latestConfig.llm_config.llm_provider,
                          llm_model: latestConfig.llm_config.llm_model,
                          api_token: latestConfig.llm_config.api_token ? "••••••••••••••••" : "",
                          azure_endpoint: latestConfig.llm_config.azure_endpoint,
                          azure_deployment: latestConfig.llm_config.azure_deployment,
                          api_version: latestConfig.llm_config.api_version
                        }, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* Google Form */}
            {sourceType === 'google' && (
              <div className="mb-8">
                <h3 className="font-medium mb-3">Google Services Configuration:</h3>
                
                <div className="space-y-4 mb-6">
                  <div className="p-4 bg-gray-50 rounded-md border border-gray-200">
                    <h4 className="text-sm font-medium mb-3">Google Authentication:</h4>
                    
                    <div className="mb-4">
                      <div id="googleAuthStatus" className="text-sm text-gray-600 mb-3">
                        {isLoadingGoogleAuth ? (
                          <span className="flex items-center">
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Checking authentication status...
                          </span>
                        ) : googleAuthStatus ? (
                          googleAuthStatus.is_authenticated ? (
                            <span className="flex items-center text-green-600">
                              <svg className="h-4 w-4 mr-1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                              </svg>
                              {googleAuthStatus.message}
                            </span>
                          ) : (
                            <span className="flex items-center text-orange-600">
                              <svg className="h-4 w-4 mr-1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                              </svg>
                              {googleAuthStatus.message}
                            </span>
                          )
                        ) : (
                          <span>Unknown authentication status</span>
                        )}
                      </div>
                      
                      <div className="flex space-x-2">
                        {googleAuthStatus && !googleAuthStatus.is_authenticated ? (
                          <button
                            type="button"
                            onClick={handleGoogleLogin}
                            className="flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                          >
                            <svg className="h-5 w-5 mr-2" viewBox="0 0 24 24">
                              <path
                                fill="#4285F4"
                                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                              />
                              <path
                                fill="#34A853"
                                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                              />
                              <path
                                fill="#FBBC05"
                                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                              />
                              <path
                                fill="#EA4335"
                                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                              />
                            </svg>
                            Login with Google
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={handleGoogleLogout}
                            className="flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                          >
                            Logout from Google
                          </button>
                        )}
                        
                        <button
                          type="button"
                          onClick={handleTestGoogleConnection}
                          disabled={!googleAuthStatus || !googleAuthStatus.is_authenticated}
                          className={`flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${
                            !googleAuthStatus || !googleAuthStatus.is_authenticated
                              ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                              : 'text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
                          }`}
                        >
                          Test Connection
                        </button>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Select Google Services to Connect:
                    </label>
                    <div className="space-y-2">
                      <div className="flex items-center">
                        <input
                          type="checkbox"
                          id="drive"
                          checked={googleConfig.services.includes('drive')}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setGoogleConfig({
                                ...googleConfig,
                                services: [...googleConfig.services, 'drive']
                              });
                            } else {
                              setGoogleConfig({
                                ...googleConfig,
                                services: googleConfig.services.filter(s => s !== 'drive')
                              });
                            }
                          }}
                          disabled={!googleAuthStatus || !googleAuthStatus.is_authenticated}
                          className="h-4 w-4 text-blue-600"
                        />
                        <label htmlFor="drive" className={`ml-2 text-sm ${!googleAuthStatus || !googleAuthStatus.is_authenticated ? 'text-gray-400' : 'text-gray-700'}`}>
                          Google Drive
                        </label>
                      </div>
                      
                      <div className="flex items-center">
                        <input
                          type="checkbox"
                          id="gmail"
                          checked={googleConfig.services.includes('gmail')}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setGoogleConfig({
                                ...googleConfig,
                                services: [...googleConfig.services, 'gmail']
                              });
                            } else {
                              setGoogleConfig({
                                ...googleConfig,
                                services: googleConfig.services.filter(s => s !== 'gmail')
                              });
                            }
                          }}
                          disabled={!googleAuthStatus || !googleAuthStatus.is_authenticated}
                          className="h-4 w-4 text-blue-600"
                        />
                        <label htmlFor="gmail" className={`ml-2 text-sm ${!googleAuthStatus || !googleAuthStatus.is_authenticated ? 'text-gray-400' : 'text-gray-700'}`}>
                          Gmail
                        </label>
                      </div>
                      
                      <div className="flex items-center">
                        <input
                          type="checkbox"
                          id="photos"
                          checked={googleConfig.services.includes('photos')}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setGoogleConfig({
                                ...googleConfig,
                                services: [...googleConfig.services, 'photos']
                              });
                            } else {
                              setGoogleConfig({
                                ...googleConfig,
                                services: googleConfig.services.filter(s => s !== 'photos')
                              });
                            }
                          }}
                          disabled={!googleAuthStatus || !googleAuthStatus.is_authenticated}
                          className="h-4 w-4 text-blue-600"
                        />
                        <label htmlFor="photos" className={`ml-2 text-sm ${!googleAuthStatus || !googleAuthStatus.is_authenticated ? 'text-gray-400' : 'text-gray-700'}`}>
                          Google Photos
                        </label>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <label htmlFor="max_items" className="block text-sm font-medium text-gray-700 mb-1">
                      Maximum Items per Service:
                    </label>
                    <input
                      type="number"
                      id="max_items"
                      value={googleConfig.max_items}
                      onChange={(e) => setGoogleConfig({
                        ...googleConfig,
                        max_items: parseInt(e.target.value) || 50
                      })}
                      disabled={!googleAuthStatus || !googleAuthStatus.is_authenticated}
                      min="1"
                      max="500"
                      className={`w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none ${
                        !googleAuthStatus || !googleAuthStatus.is_authenticated
                          ? 'bg-gray-100 text-gray-400'
                          : 'focus:ring-blue-500 focus:border-blue-500'
                      }`}
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Limits how many items to fetch from each selected service
            </p>
          </div>
        </div>
              </div>
            )}
        
        {/* Submit Button */}
            <div className="mt-8 flex justify-center space-x-4">
          <button
            type="submit"
            disabled={isLoading}
                className="px-6 py-3 bg-blue-600 text-black font-medium rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {isLoading ? (
                  <span className="flex items-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-black" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Processing...
                  </span>
                ) : 'Save Configuration'}
              </button>

              {sourceType === 'google' && (
                <button
                  type="button"
                  onClick={ingestGoogleData}
                  disabled={!googleAuthStatus || !googleAuthStatus.is_authenticated || !latestConfig || isIngestingGoogle || googleConfig.services.length === 0}
                  className={`px-6 py-3 font-medium rounded-md shadow-sm text-black ${
                    !googleAuthStatus || !googleAuthStatus.is_authenticated || !latestConfig || googleConfig.services.length === 0
                      ? 'bg-gray-300 cursor-not-allowed'
                      : isIngestingGoogle
                      ? 'bg-blue-400 cursor-wait'
                      : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
                  }`}
                >
                  {isIngestingGoogle ? (
                    <span className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-black" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                      Ingesting...
              </span>
                  ) : 'Ingest Google Data'}
          </button>
              )}
        </div>
        
        {/* Status Messages */}
        {message && (
              <div className="mt-4 p-3 bg-green-100 text-green-700 rounded-md flex items-center">
                <svg className="h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
            {message}
          </div>
        )}
        
        {error && (
              <div className="mt-4 p-3 bg-red-100 text-red-700 rounded-md flex items-center">
                <svg className="h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
            Error: {error}
          </div>
        )}
      </form>
        </div>
      </div>
    </div>
  );
};

export default DataSourceConfig; 