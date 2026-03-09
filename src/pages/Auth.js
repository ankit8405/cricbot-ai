import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const Auth = ({ setIsLoggedIn }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');

    try {
      const response = await fetch('http://127.0.0.1:8000/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();

      if (response.ok && data.success) {
        localStorage.setItem('user', JSON.stringify(data.user));
        localStorage.setItem('isLoggedIn', 'true');

        if (typeof setIsLoggedIn === 'function') {
          setIsLoggedIn(true);
        }

        navigate('/home');
      } else {
        setErrorMsg(data.message || 'Login failed');
      }
    } catch (error) {
      setErrorMsg('Network error. Try again later.');
    }
  };

  return (
    <div style={styles.container}>
      <h2>Sign In</h2>
      <form onSubmit={handleSubmit} style={styles.form}>
        <label style={styles.label}>
          Username:
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            style={styles.input}
            placeholder="Enter your username"
          />
        </label>

        <label style={styles.label}>
          Password:
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={styles.input}
            placeholder="Enter your password"
          />
        </label>

        {errorMsg && <p style={{ color: 'red' }}>{errorMsg}</p>}

        <button type="submit" style={styles.button}>
          Sign In
        </button>
      </form>

      <p style={styles.registerText}>New to BOTai?</p>
      <button style={styles.secondaryButton} onClick={() => navigate('/register')}>
        Create New Account
      </button>
    </div>
  );
};

const styles = {
  container: {
    maxWidth: '400px',
    margin: '3rem auto',
    padding: '2rem',
    border: '1px solid #ccc',
    borderRadius: '8px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
    backgroundColor: 'white',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
  },
  label: {
    marginBottom: '1rem',
    fontSize: '1rem',
  },
  input: {
    width: '100%',
    padding: '0.6rem',
    marginTop: '0.4rem',
    fontSize: '1rem',
    borderRadius: '4px',
    border: '1px solid #ccc',
    boxSizing: 'border-box',
  },
  button: {
    padding: '0.75rem',
    backgroundColor: '#060631',
    color: 'white',
    fontSize: '1rem',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    marginTop: '1rem',
  },
  registerText: {
    marginTop: '1.5rem',
    fontSize: '1rem',
    textAlign: 'center',
  },
  secondaryButton: {
    marginTop: '0.5rem',
    padding: '0.65rem',
    backgroundColor: '#f0f0f0',
    color: '#060631',
    fontSize: '1rem',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    width: '100%',
  },
};

export default Auth;
