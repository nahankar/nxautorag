import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const QueryInterface = ({ setAnswer, setIsLoading: setGlobalIsLoading, setError: setGlobalError }) => {
  const [query, setQuery] = useState('');
  const [sources, setSources] = useState([]);
  const [showSources, setShowSources] = useState(false);
  const [localAnswer, setLocalAnswer] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchOption, setSearchOption] = useState('local_semantic');
  const navigate = useNavigate();

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setGlobalIsLoading(true);
    setError('');
    setAnswer('');
    setSources([]);
    
    try {
      // Extract storage type and search method from searchOption
      const storageType = searchOption.startsWith('google_drive_') ? 'google_drive' : 'local';
      const searchMethod = searchOption.includes('hybrid') ? 'hybrid' : 
                           searchOption.includes('reranking') ? 'reranking' : 'semantic';
      
      const response = await axios.post('http://localhost:8000/query', {
        question: query,
        include_sources: showSources,
        search_option: searchMethod,
        storage_type: storageType
      });
      
      setLocalAnswer(response.data.answer || '');
      if (response.data.sources) {
        setSources(response.data.sources);
      }
      setAnswer(response.data.answer || '');
    } catch (err) {
      console.error('Error querying:', err);
      setError(err.response?.data?.message || err.message || 'Failed to get response');
      setGlobalError(err.response?.data?.message || err.message || 'Failed to get response');
    } finally {
      setIsLoading(false);
      setGlobalIsLoading(false);
    }
  };

  // Handle using agent for query
  const handleUseAgent = async () => {
    if (!query.trim()) return;
    
    setIsLoading(true);
    setGlobalIsLoading(true);
    setError('');
    setGlobalError('');
    
    try {
      // Extract storage type and search method from searchOption
      const storageType = searchOption.startsWith('google_drive_') ? 'google_drive' : 'local';
      const searchMethod = searchOption.includes('hybrid') ? 'hybrid' : 
                           searchOption.includes('reranking') ? 'reranking' : 'semantic';
                           
      // Send request to agent endpoint
      const response = await axios.post('http://localhost:8000/agent-query', { 
        question: query,
        search_option: searchMethod,
        storage_type: storageType
      });
      
      if (response.data.answer) {
        setLocalAnswer(response.data.answer);
        setAnswer(response.data.answer);
        // Optionally navigate to results page
        // navigate('/results');
      } else if (response.data.status === 'error') {
        setError(response.data.message);
        setGlobalError(response.data.message);
      }
    } catch (err) {
      const errorMsg = err.response?.data?.message || err.message || 'An error occurred';
      setError(errorMsg);
      setGlobalError(errorMsg);
    } finally {
      setIsLoading(false);
      setGlobalIsLoading(false);
    }
  };

  // Clear form
  const handleClear = () => {
    setQuery('');
    setLocalAnswer('');
    setError('');
    // Clear global state too
    setAnswer('');
    setGlobalError('');
    setSources([]);
  };

  // View results in dedicated page
  const handleViewResults = () => {
    navigate('/results');
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex flex-col md:flex-row gap-6">
        {/* Left column - Query input */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 md:w-1/2 flex flex-col">
          <h2 className="text-2xl font-bold mb-6">Query Your Data</h2>
          
          <form onSubmit={handleSubmit} className="flex flex-col flex-grow">
            <div className="mb-6 flex-grow">
              <label htmlFor="query" className="block text-sm font-medium text-gray-700 mb-2">
                Enter your question:
              </label>
              <textarea
                id="query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={4}
                className="w-full h-[150px] px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="Ask anything about your data..."
                required
              />
            </div>
            
            <div className="mb-6">
              <div className="flex items-center">
                <input
                  id="showSources"
                  type="checkbox"
                  checked={showSources}
                  onChange={(e) => setShowSources(e.target.checked)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="showSources" className="ml-2 block text-sm text-gray-700">
                  Include sources in response
                </label>
              </div>
            </div>
            
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Retrieve from:
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="flex items-center">
                  <input
                    id="local-storage"
                    type="radio"
                    name="storage-option"
                    value="local"
                    checked={searchOption.startsWith('local_')}
                    onChange={() => {
                      // Keep the search method, just change the storage prefix
                      const method = searchOption.split('_')[1] || 'semantic';
                      setSearchOption(`local_${method}`);
                    }}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                  />
                  <label htmlFor="local-storage" className="ml-2 block text-sm text-gray-700">
                    Local Storage
                  </label>
                </div>
                <div className="flex items-center">
                  <input
                    id="google-drive-storage"
                    type="radio"
                    name="storage-option"
                    value="google_drive"
                    checked={searchOption.startsWith('google_drive_')}
                    onChange={() => {
                      // Keep the search method, just change the storage prefix
                      const method = searchOption.split('_')[2] || 'semantic';
                      setSearchOption(`google_drive_${method}`);
                    }}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                  />
                  <label htmlFor="google-drive-storage" className="ml-2 block text-sm text-gray-700">
                    Google Drive
                  </label>
                </div>
              </div>
            </div>
            
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Search Method:
              </label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="flex items-center">
                  <input
                    id="semantic"
                    type="radio"
                    name="search-option"
                    value="semantic"
                    checked={searchOption.includes('semantic')}
                    onChange={() => {
                      // Keep the storage prefix, just change the method
                      const prefix = searchOption.startsWith('google_drive_') ? 'google_drive_' : 'local_';
                      setSearchOption(`${prefix}semantic`);
                    }}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                  />
                  <label htmlFor="semantic" className="ml-2 block text-sm text-gray-700">
                    Semantic (KNN)
                  </label>
                </div>
                <div className="flex items-center">
                  <input
                    id="hybrid"
                    type="radio"
                    name="search-option"
                    value="hybrid"
                    checked={searchOption.includes('hybrid')}
                    onChange={() => {
                      // Keep the storage prefix, just change the method
                      const prefix = searchOption.startsWith('google_drive_') ? 'google_drive_' : 'local_';
                      setSearchOption(`${prefix}hybrid`);
                    }}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                  />
                  <label htmlFor="hybrid" className="ml-2 block text-sm text-gray-700">
                    Hybrid (Sparse+Dense)
                  </label>
                </div>
                <div className="flex items-center">
                  <input
                    id="reranking"
                    type="radio"
                    name="search-option"
                    value="reranking"
                    checked={searchOption.includes('reranking')}
                    onChange={() => {
                      // Keep the storage prefix, just change the method
                      const prefix = searchOption.startsWith('google_drive_') ? 'google_drive_' : 'local_';
                      setSearchOption(`${prefix}reranking`);
                    }}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300"
                  />
                  <label htmlFor="reranking" className="ml-2 block text-sm text-gray-700">
                    Re-Ranking
                  </label>
                </div>
              </div>
            </div>
            
            <div className="flex justify-center mt-auto">
              <button
                type="submit"
                className="px-6 py-3 bg-blue-600 text-black font-medium rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Submit Query
              </button>
            </div>
          </form>
        </div>
        
        {/* Right column - Answer */}
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 md:w-1/2 flex flex-col min-h-[350px]">
          <h2 className="text-2xl font-bold mb-6">Answer</h2>
          
          <div className="flex-grow flex items-start">
            {isLoading ? (
              <div className="w-full h-full flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
              </div>
            ) : localAnswer ? (
              <div className="whitespace-pre-wrap overflow-auto">{localAnswer}</div>
            ) : (
              <div className="text-gray-500 italic">Your answer will appear here after you submit a query.</div>
            )}
          </div>
          
          {showSources && sources.length > 0 && (
            <div className="mt-6 border-t pt-4">
              <h3 className="text-lg font-semibold mb-2">Sources:</h3>
              {sources.map((source, index) => (
                <div key={index} className="text-sm text-gray-500 mb-2 bg-gray-50 p-2 rounded">{source}</div>
              ))}
            </div>
          )}
        </div>
      </div>
      
      {error && (
        <div className="bg-red-100 p-4 rounded-lg text-red-700 mt-6">
          <h3 className="font-semibold text-lg mb-2">Error:</h3>
          <div>{error}</div>
        </div>
      )}
    </div>
  );
};


export default QueryInterface; 