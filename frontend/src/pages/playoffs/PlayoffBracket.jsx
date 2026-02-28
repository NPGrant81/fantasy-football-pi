import React from 'react';
import BracketAccordion from '../home/components/BracketAccordion';

export default function PlayoffBracket() {
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Playoff Bracket</h1>
      {/* reuse the accordion component so the logic for fetching/formatting stays in one place */}
      <BracketAccordion />
    </div>
  );
}
