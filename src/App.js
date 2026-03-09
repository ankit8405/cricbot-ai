import React, { useState, useEffect } from 'react';
import { Routes, Route, useLocation, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import About from './pages/About';
import Contact from './pages/Contact';
import Auth from './pages/Auth';
import Register from './pages/Register';
import Feedback from './pages/Feedback';
import Landing from './pages/Landing';
import Chatbot from './components/Chatbot';

const App = () => {
  const location = useLocation();

  const [isLoggedIn, setIsLoggedIn] = useState(() => {
    return localStorage.getItem('isLoggedIn') === 'true';
  });

  useEffect(() => {
    const storedStatus = localStorage.getItem('isLoggedIn') === 'true';
    if (storedStatus !== isLoggedIn) {
      setIsLoggedIn(storedStatus);
    }
  }, [isLoggedIn]);

  return (
    <>
      <Navbar isLoggedIn={isLoggedIn} setIsLoggedIn={setIsLoggedIn} />

      <Routes>
        <Route
          path="/"
          element={isLoggedIn ? <Navigate to="/home" replace /> : <Landing />}
        />

        <Route
          path="/auth"
          element={isLoggedIn ? <Navigate to="/home" replace /> : <Auth setIsLoggedIn={setIsLoggedIn} />}
        />
        <Route path="/register" element={<Register />} />

        <Route
          path="/home"
          element={isLoggedIn ? <Home /> : <Navigate to="/auth" replace />}
        />
        <Route
          path="/about"
          element={isLoggedIn ? <About /> : <Navigate to="/auth" replace />}
        />
        <Route
          path="/contact"
          element={isLoggedIn ? <Contact /> : <Navigate to="/auth" replace />}
        />
        <Route
          path="/feedback"
          element={isLoggedIn ? <Feedback /> : <Navigate to="/auth" replace />}
        />
        <Route
          path="/chatbot"
          element={isLoggedIn ? <Chatbot /> : <Navigate to="/auth" replace />}
        />
      </Routes>
    </>
  );
};

export default App;
