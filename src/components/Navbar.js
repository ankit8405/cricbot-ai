import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import './Navbar.css';
import logo from '../assets/botlogo.png';

const Navbar = ({ isLoggedIn, setIsLoggedIn }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const isLanding = location.pathname === '/';

  const handleSignOut = () => {
    localStorage.removeItem('isLoggedIn');
    setIsLoggedIn(false);
    navigate('/');
  };

  if (isLanding || !isLoggedIn) {
    return null;
  }

  return (
    <nav className="navbar" role="navigation" aria-label="Main Navigation">
      <Link to="/home" className="navbar-logo">
        <img src={logo} alt="AI Logo" className="logo-img" />
        <span className="logo-text">CricBOTai</span>
      </Link>

      <div className="nav-links">
        <Link to="/home" className="nav-link">Home</Link>
        <Link to="/chatbot" className="nav-link">Chatbot</Link>
        <Link to="/about" className="nav-link">About</Link>
        <Link to="/contact" className="nav-link">Contact</Link>
        <button
          onClick={handleSignOut}
          className="nav-link signout-button"
          type="button"
          aria-label="Sign Out"
        >
          Sign Out
        </button>
      </div>
    </nav>
  );
};

export default Navbar;
