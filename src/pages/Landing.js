import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const Landing = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const loggedIn = localStorage.getItem('isLoggedIn') === 'true';
    if (loggedIn) {
      navigate('/home');
    }

    document.body.style.paddingTop = '0';

    return () => {
      document.body.style.paddingTop = '60px';
    };
  }, [navigate]);

  return (
    <div className="landing-page">
      <h1 className="landing-title">Welcome to BOTai</h1>
      <p className="landing-text">Your personal AI-powered assistant.</p>
      <button className="landing-button" onClick={() => navigate('/auth')}>
        Sign In
      </button>
    </div>
  );
};

export default Landing;
