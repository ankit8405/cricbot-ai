import React from 'react';
import botImage from '../assets/bot.jpg';

const About = () => {
  return (
    <div className="about-container">
      <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
        <h2>About Me</h2>
        <p>
          Hi, I'm <strong>Ankit</strong> — a 3rd year undergraduate student in Computer Science and Engineering with an interest in machine learning and backend development. <strong>CricBOTai</strong> is a personal project where I've built a responsive, AI-powered chatbot website using <strong>React.js and FastAPI</strong>.
        </p>

        <div style={{ margin: '1.5rem 0', textAlign: 'center' }}>
          <img
            src={botImage}
            alt="BOTai Illustration"
            style={{
              maxWidth: '100%',
              height: 'auto',
              borderRadius: '8px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
            }}
          />
        </div>

        <p>
          The chatbot is designed to offer real-time assistance through a smooth, user-friendly interface. It slides in seamlessly when needed and automatically scrolls through conversations for an effortless experience.
        </p>
        <p>
          Whether you're here to explore, ask questions, or check out what I’ve built — I hope you enjoy interacting with it as much as I enjoyed creating it.
        </p>
      </div>
    </div>
  );
};

export default About;
