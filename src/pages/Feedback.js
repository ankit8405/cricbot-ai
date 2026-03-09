import React, { useState } from 'react';

const Feedback = () => {
  const [feedbackText, setFeedbackText] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (feedbackText.trim() === '') {
      alert('Please enter your feedback before submitting.');
      return;
    }
    alert('Thank you for your feedback!');
    setFeedbackText('');
  };

  return (
    <div style={{ maxWidth: '600px', margin: '2rem auto', padding: '1rem', color: '#333' }}>
      <h1>Feedback</h1>
      <p style={{ marginBottom: '0.75rem' }}>
      Please share your feedback below:
      </p>
      <form onSubmit={handleSubmit}>
        <textarea
          value={feedbackText}
          onChange={(e) => setFeedbackText(e.target.value)}
          rows={6}
          style={{
            width: '100%',
            padding: '1rem',
            fontSize: '1rem',
            borderRadius: '5px',
            border: '1px solid #ccc',
            resize: 'vertical',
          }}
          placeholder="Write your feedback here..."
        />
        <button
          type="submit"
          style={{
            marginTop: '1rem',
            padding: '0.75rem 1.5rem',
            fontSize: '1rem',
            backgroundColor: '#4a90e2',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer',
          }}
        >
          Submit Feedback
        </button>
      </form>
    </div>
  );
};

export default Feedback;
