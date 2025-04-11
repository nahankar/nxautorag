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

  // Storage configuration
  const [storageConfig, setStorageConfig] = useState({
    type: 'local'
  });
  const [storageOptions, setStorageOptions] = useState([]);
  const [isLoadingStorageOptions, setIsLoadingStorageOptions] = useState(false);

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
    fetchStorageOptions();
  }, [sourceType]);

  // Check Google auth status when Google tab is selected
  useEffect(() => {
    if (sourceType === 'google') {
      checkGoogleAuthStatus();
    }
  }, [sourceType]);
  
  // Make sure Drive is selected after authentication is successful
  useEffect(() => {
    if (googleAuthStatus && googleAuthStatus.is_authenticated) {
      // Ensure 'drive' is in services if authenticated and not already there
      if (!googleConfig.services.includes('drive')) {
        setGoogleConfig(prev => ({
          ...prev,
          services: [...prev.services, 'drive']
        }));
      }
    }
  }, [googleAuthStatus]);

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

  // Fetch storage options
  const fetchStorageOptions = async () => {
    setIsLoadingStorageOptions(true);
    try {
      const response = await axios.get('http://localhost:8000/storage-options');
      if (response.data && response.data.status === 'success') {
        setStorageOptions(response.data.options || []);
      }
    } catch (err) {
      console.error('Failed to fetch storage options:', err);
      setStorageOptions([
        {
          id: 'local',
          name: 'Local Storage',
          description: 'Store vectorstore on the local server',
          available: true
        }
      ]);
    } finally {
      setIsLoadingStorageOptions(false);
    }
  };

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
        } else if (sourceType === 'google' && response.data.google_config) {
          // Make sure to properly set the google config including services
          setGoogleConfig(response.data.google_config);
          
          // Ensure 'drive' is included if authenticated
          if (googleAuthStatus && googleAuthStatus.is_authenticated && 
              !response.data.google_config.services.includes('drive')) {
            setGoogleConfig(prev => ({
              ...prev,
              services: [...(prev.services || []), 'drive']
            }));
          }
        }

        // Set storage config if available
        if (response.data.storage_config) {
          setStorageConfig(response.data.storage_config);
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

  const handleStorageChange = (e) => {
    setStorageConfig({ ...storageConfig, type: e.target.value });
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
      
      // Prepare configuration object
      const configObject = {
        sourceType: sourceType,
        storage_config: storageConfig  // Add storage config
      };
      
      // Add selected source config
      if (sourceType === 'mysql') {
        configObject.mysql_config = mysqlConfig;
      } else if (sourceType === 'url') {
        configObject.url_config = urlConfig;
      } else if (sourceType === 'google') {
        configObject.google_config = googleConfig;
      } else if (sourceType === 'llm') {
        configObject.llm_config = llmConfig;
      }
      
      // If using Google Drive storage but not authenticated
      if (storageConfig.type === 'google_drive' && 
          (!googleAuthStatus || !googleAuthStatus.is_authenticated)) {
        setError("You must be authenticated with Google to use Google Drive storage.");
        setIsLoading(false);
        return;
      }
      
      let response;
      
      // Use different endpoint for LLM settings
      if (sourceType === 'llm') {
        // For LLM settings, use dedicated endpoint without form data
        response = await axios.post('http://localhost:8000/save-llm-settings', configObject);
      } else {
        // Add files if file source selected
        if (sourceType === 'file' && files.length > 0) {
          files.forEach(file => {
            formData.append('files', file);
          });
        }
        
        // Always include LLM config
        configObject.llm_config = llmConfig;
        
        // Add config as JSON string
        formData.append('config', JSON.stringify(configObject));
        
        // Send to server using the ingest endpoint for documents
        response = await axios.post('http://localhost:8000/ingest', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        });
      }
      
      // Handle response from server
      if (response.data.status === 'success') {
        if (sourceType === 'llm') {
          setMessage('✅ LLM Settings saved successfully! Your RAG system will use these settings for generating responses.');
        } else {
          // Calculate total document count
          const documentCount = response.data.document_count || 0;
          const chunkCount = response.data.chunk_count || 0;
          const storageType = response.data.storage_type === 'google_drive' ? 'Google Drive' : 'local storage';
          
          setMessage(
            `✅ Data ingestion successful! Processed ${documentCount} documents into ${chunkCount} chunks. ` +
            `Vectorstore saved to ${storageType}.`
          );
        }
      } else {
        setError(`Error: ${response.data.detail || 'Unknown error occurred'}`);
      }
    } catch (err) {
      console.error('Ingestion error:', err);
      setError(`Error: ${err.response?.data?.detail || err.message || 'Unknown error occurred'}`);
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

  const renderStorageOptions = () => (
    <div className="mt-4 p-4 bg-white rounded-lg shadow-sm">
      <h3 className="text-lg font-semibold mb-3">Storage Configuration</h3>
      <div className="mb-3">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Where to store vectorstore:
        </label>
        <div className="grid gap-3">
          {isLoadingStorageOptions ? (
            <div className="text-gray-500">Loading storage options...</div>
          ) : (
            storageOptions.map(option => (
              <div key={option.id} className="flex items-start">
                <input
                  type="radio"
                  id={`storage-${option.id}`}
                  name="storage-type"
                  value={option.id}
                  checked={storageConfig.type === option.id}
                  onChange={handleStorageChange}
                  disabled={!option.available}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                />
                <label htmlFor={`storage-${option.id}`} className="ml-2 block">
                  <div className="font-medium text-gray-800">{option.name}</div>
                  <div className="text-sm text-gray-500">{option.description}</div>
                  {!option.available && (
                    <div className="text-xs text-red-500 mt-1">{option.message || 'Not available'}</div>
                  )}
                </label>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Data Source Configuration</h1>
      
      <div className="bg-white p-6 rounded-lg shadow-md">
        <div className="flex border-b mb-6">
          <button
            className={`px-4 py-2 border-b-2 ${sourceType === 'file' ? 'border-blue-500 text-blue-600' : 'border-transparent'}`}
            onClick={() => setSourceType('file')}
          >
            File Upload
          </button>
          <button
            className={`px-4 py-2 border-b-2 ${sourceType === 'mysql' ? 'border-blue-500 text-blue-600' : 'border-transparent'}`}
            onClick={() => setSourceType('mysql')}
          >
            MySQL
          </button>
          <button
            className={`px-4 py-2 border-b-2 ${sourceType === 'url' ? 'border-blue-500 text-blue-600' : 'border-transparent'}`}
            onClick={() => setSourceType('url')}
          >
            URL
          </button>
          <button
            className={`px-4 py-2 border-b-2 ${sourceType === 'google' ? 'border-blue-500 text-blue-600' : 'border-transparent'}`}
            onClick={() => setSourceType('google')}
          >
            Google Services
          </button>
          <button
            className={`px-4 py-2 border-b-2 ${sourceType === 'llm' ? 'border-blue-500 text-blue-600' : 'border-transparent'}`}
            onClick={() => setSourceType('llm')}
          >
            LLM Settings
          </button>
        </div>
        
        <form onSubmit={handleSubmit}>
          {/* Source-specific configuration */}
          {sourceType === 'file' && (
            <div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Upload Documents (PDF, DOCX, TXT)
                </label>
                <input
                  id="file-upload"
                  type="file"
                  multiple
                  accept=".pdf,.docx,.txt"
                  onChange={handleFileChange}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
                {files.length > 0 && (
                  <div className="mt-2">
                    <p className="text-sm text-gray-600">Selected {files.length} file(s):</p>
                    <ul className="list-disc pl-5 mt-1 text-sm text-gray-600">
                      {files.map((file, index) => (
                        <li key={index}>{file.name} ({Math.round(file.size / 1024)} KB)</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              
              {/* Add storage options */}
              {renderStorageOptions()}
            </div>
          )}
          
          {sourceType === 'mysql' && (
            <div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Host
                  </label>
                  <input
                    type="text"
                    name="host"
                    value={mysqlConfig.host}
                    onChange={handleMysqlChange}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    placeholder="localhost"
                    required
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Port
                  </label>
                  <input
                    type="number"
                    name="port"
                    value={mysqlConfig.port}
                    onChange={handleMysqlChange}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    placeholder="3306"
                    required
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Username
                  </label>
                  <input
                    type="text"
                    name="user"
                    value={mysqlConfig.user}
                    onChange={handleMysqlChange}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    placeholder="root"
                    required
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      type={showDbPassword ? "text" : "password"}
                      name="password"
                      value={mysqlConfig.password}
                      onChange={handleMysqlChange}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      required
                    />
                    <button
                      type="button"
                      onClick={toggleDbPasswordVisibility}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-sm text-gray-500"
                    >
                      {showDbPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                </div>
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Database
                </label>
                <input
                  type="text"
                  name="database"
                  value={mysqlConfig.database}
                  onChange={handleMysqlChange}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  placeholder="mydatabase"
                  required
                />
              </div>
              
              {/* Add storage options */}
              {renderStorageOptions()}
            </div>
          )}
          
          {sourceType === 'url' && (
            <div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Web URL
                </label>
                <input
                  type="url"
                  value={urlConfig.url}
                  onChange={handleUrlChange}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  placeholder="https://example.com/page-to-ingest"
                  required
                />
              </div>
              
              {/* Add storage options */}
              {renderStorageOptions()}
            </div>
          )}
          
          {sourceType === 'google' && (
            <div>
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
                          checked={googleConfig.services?.includes('drive')}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setGoogleConfig({
                                ...googleConfig,
                                services: [...(googleConfig.services || []), 'drive']
                              });
                            } else {
                              setGoogleConfig({
                                ...googleConfig,
                                services: (googleConfig.services || []).filter(s => s !== 'drive')
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
                          checked={googleConfig.services?.includes('gmail')}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setGoogleConfig({
                                ...googleConfig,
                                services: [...(googleConfig.services || []), 'gmail']
                              });
                            } else {
                              setGoogleConfig({
                                ...googleConfig,
                                services: (googleConfig.services || []).filter(s => s !== 'gmail')
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
                          checked={googleConfig.services?.includes('photos')}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setGoogleConfig({
                                ...googleConfig,
                                services: [...(googleConfig.services || []), 'photos']
                              });
                            } else {
                              setGoogleConfig({
                                ...googleConfig,
                                services: (googleConfig.services || []).filter(s => s !== 'photos')
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
              
              {googleAuthStatus && googleAuthStatus.is_authenticated && renderStorageOptions()}
            </div>
          )}
          
          {sourceType === 'llm' && (
            <div>
              <div className="mb-4">
                <h3 className="text-lg font-semibold mb-4">LLM Provider Configuration</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      LLM Provider
                    </label>
                    <select
                      name="llm_provider"
                      value={llmConfig.llm_provider}
                      onChange={handleLlmChange}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    >
                      <option value="local">Local (GGUF)</option>
                      <option value="openai">OpenAI</option>
                      <option value="anthropic">Anthropic</option>
                      <option value="azure">Azure</option>
                      <option value="huggingface">HuggingFace</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Model Name
                    </label>
                    <input
                      type="text"
                      name="llm_model"
                      value={llmConfig.llm_model}
                      onChange={handleLlmChange}
                      placeholder={llmConfig.llm_provider === 'local' ? 'mistralai/Mixtral-8x7B-Instruct-v0.1' : 
                                  llmConfig.llm_provider === 'openai' ? 'gpt-4' : 
                                  llmConfig.llm_provider === 'anthropic' ? 'claude-3-opus-20240229' :
                                  llmConfig.llm_provider === 'azure' ? llmConfig.azure_deployment || 'deployment-name' :
                                  'model-name'}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    />
                  </div>
                </div>
                
                {(llmConfig.llm_provider === 'openai' || llmConfig.llm_provider === 'anthropic' || llmConfig.llm_provider === 'huggingface') && (
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      API Key
                    </label>
                    <div className="relative">
                      <input
                        type={showApiToken ? "text" : "password"}
                        name="api_token"
                        value={llmConfig.api_token}
                        onChange={handleLlmChange}
                        placeholder="Enter your API key"
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      />
                      <button
                        type="button"
                        onClick={toggleApiTokenVisibility}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center text-sm text-gray-500"
                      >
                        {showApiToken ? "Hide" : "Show"}
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Your API key will be stored on your server and not shared.
                    </p>
                  </div>
                )}
                
                {llmConfig.llm_provider === 'azure' && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Azure Endpoint
                      </label>
                      <input
                        type="text"
                        name="azure_endpoint"
                        value={llmConfig.azure_endpoint}
                        onChange={handleLlmChange}
                        placeholder="https://your-resource-name.openai.azure.com"
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Azure Deployment Name
                      </label>
                      <input
                        type="text"
                        name="azure_deployment"
                        value={llmConfig.azure_deployment}
                        onChange={handleLlmChange}
                        placeholder="your-deployment-name"
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        API Version
                      </label>
                      <input
                        type="text"
                        name="api_version"
                        value={llmConfig.api_version}
                        onChange={handleLlmChange}
                        placeholder="2023-12-01-preview"
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        API Key
                      </label>
                      <div className="relative">
                        <input
                          type={showApiToken ? "text" : "password"}
                          name="api_token"
                          value={llmConfig.api_token}
                          onChange={handleLlmChange}
                          placeholder="Enter your Azure API key"
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                        />
                        <button
                          type="button"
                          onClick={toggleApiTokenVisibility}
                          className="absolute inset-y-0 right-0 pr-3 flex items-center text-sm text-gray-500"
                        >
                          {showApiToken ? "Hide" : "Show"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
              
              <div className="mt-6">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="inline-flex justify-center py-2 px-4 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-black bg-white hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50"
                >
                  {isLoading ? 'Saving...' : 'Save LLM Settings'}
                </button>
              </div>
            </div>
          )}
          
          {/* Always show submit button unless in LLM settings */}
          {sourceType !== 'llm' && (
            <div className="mt-6">
              <button
                type="submit"
                disabled={isLoading}
                className="inline-flex justify-center py-2 px-4 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-black bg-white hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50"
              >
                {isLoading ? 'Processing...' : 'Ingest Data'}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};

export default DataSourceConfig; 