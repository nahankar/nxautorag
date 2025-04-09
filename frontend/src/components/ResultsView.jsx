import React from 'react';

const ResultsView = ({ answer, isLoading, error }) => {
  return (
    <div className="max-w-4xl mx-auto p-6">
      <h2 className="text-2xl font-bold mb-6">Results</h2>
      
      {isLoading ? (
        <div className="flex justify-center items-center p-12">
          <svg className="animate-spin h-10 w-10 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>
      ) : (
        <>
          {answer ? (
            <div className="bg-white shadow-md rounded-lg overflow-hidden">
              <div className="p-6">
                <h3 className="text-xl font-semibold mb-4">Answer</h3>
                <div className="prose max-w-none">
                  <p className="whitespace-pre-wrap">{answer}</p>
                </div>
              </div>
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative" role="alert">
              <strong className="font-bold">Error: </strong>
              <span className="block sm:inline">{error}</span>
            </div>
          ) : (
            <div className="text-gray-500 text-center py-12">
              <p>No results to display yet. Try asking a question first.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ResultsView; 