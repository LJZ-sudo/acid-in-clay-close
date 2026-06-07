import { useRef, useEffect } from 'react'
import { useAgentStore } from '../../stores'
import DecisionCard from './DecisionCard'
import { LoadingSpinner } from '../common'

/**
 * Thought chain panel — Agent decision trace
 */
function ThoughtChainPanel() {
  const { thoughtChain, isThinking, clearThoughtChain } = useAgentStore()
  const containerRef = useRef(null)

  // Scroll to bottom when chain updates
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [thoughtChain])

  return (
    <div className="card h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <h3 className="font-semibold text-gray-800">Thought Chain</h3>
          {isThinking && (
            <span className="flex items-center text-xs text-primary-600">
              <LoadingSpinner size="sm" className="mr-1" />
              Thinking...
            </span>
          )}
        </div>
        
        <button
          onClick={clearThoughtChain}
          className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
        >
          Clear
        </button>
      </div>

      {/* Thought chain list */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-y-auto p-4 space-y-3"
      >
        {thoughtChain.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <svg className="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p className="text-sm">Waiting for Agent decision...</p>
            <p className="text-xs mt-1">Thought process will appear after experiment starts</p>
          </div>
        ) : (
          thoughtChain.map((thought, index) => (
            <DecisionCard
              key={thought.id}
              thought={thought}
              isLatest={index === thoughtChain.length - 1}
            />
          ))
        )}
      </div>

      {/* Footer stats */}
      {thoughtChain.length > 0 && (
        <div className="px-4 py-2 border-t border-gray-200 bg-gray-50 text-xs text-gray-500 flex justify-between">
          <span>{thoughtChain.length} steps total</span>
          <span>
            Plan: {thoughtChain.filter(t => t.type === 'plan').length} | 
            Execute: {thoughtChain.filter(t => t.type === 'action').length} | 
            Critic: {thoughtChain.filter(t => t.type === 'critic').length}
          </span>
        </div>
      )}
    </div>
  )
}

export default ThoughtChainPanel
