import React from 'react';
import { FaClock, FaBolt, FaThumbsUp } from 'react-icons/fa';
import { useNavigate, Link } from 'react-router-dom';
import '../styles/global.css';
import chatbotIcon from '../assets/redirect.png';

const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="home-container">
      <h1 className="home-title">Welcome to My Site!</h1>

      <div className="features">
        <div className="feature-item">
          <FaClock size={32} />
          <p>24/7 Support</p>
        </div>
        <div className="feature-item">
          <FaBolt size={32} />
          <p>Instant Answers</p>
        </div>
        <div className="feature-item">
          <FaThumbsUp size={32} />
          <p>Easy to Use</p>
        </div>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <button className="try-chatbot-button" onClick={() => navigate('/chatbot')}>
          <span className="button-text">Try Chatbot</span>
          <img src={chatbotIcon} alt="Chatbot icon" className="button-icon" />
        </button>
      </div>

      <div className="home-footer">
        This is a beta version — some features may be unstable or under development. Thanks for your{' '}
        <Link to="/feedback" className="feedback-link">feedback</Link>!
      </div>
    </div>
  );
};

export default Home;
