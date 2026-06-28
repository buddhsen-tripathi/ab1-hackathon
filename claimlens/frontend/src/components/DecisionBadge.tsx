import React from 'react'
import { RoutingDecision } from '../types'

interface Props {
  decision: RoutingDecision
  score?: number
  showScore?: boolean
  size?: 'sm' | 'md' | 'lg'
}

const DECISION_CONFIG = {
  auto_accept: {
    label: 'Ready to Bill',
    sub: 'auto_accept',
    bg: 'bg-green-50',
    border: 'border-green-200',
    text: 'text-green-700',
    dot: 'bg-green-500',
  },
  flag_for_review: {
    label: 'Needs Review',
    sub: 'flag_for_review',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-700',
    dot: 'bg-amber-500',
  },
  reject: {
    label: 'Not Eligible',
    sub: 'reject',
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-700',
    dot: 'bg-red-500',
  },
}

export function DecisionBadge({ decision, score, showScore = false, size = 'md' }: Props) {
  const cfg = DECISION_CONFIG[decision] || DECISION_CONFIG.reject
  const padding = size === 'sm' ? 'px-2 py-0.5' : size === 'lg' ? 'px-4 py-2' : 'px-3 py-1'
  const textSize = size === 'sm' ? 'text-xs' : size === 'lg' ? 'text-sm' : 'text-xs'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${cfg.bg} ${cfg.border} ${cfg.text} ${padding} ${textSize}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
      {showScore && score !== undefined && (
        <span className="opacity-60 font-normal">{score}/100</span>
      )}
    </span>
  )
}
