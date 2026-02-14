import { useState, useRef, useEffect } from 'react';

export function useDraftTimer(initialTime = 10, onTimeUp) {
    const [timeLeft, setTimeLeft] = useState(initialTime);
    const [isActive, setIsActive] = useState(false);
    const timerRef = useRef(null);

    const start = () => setIsActive(true);
    const reset = () => {
        setIsActive(false);
        setTimeLeft(initialTime);
        if (timerRef.current) clearInterval(timerRef.current);
    };

    useEffect(() => {
        if (isActive && timeLeft > 0) {
            timerRef.current = setInterval(() => {
                setTimeLeft(prev => prev - 1);
            }, 1000);
        } else if (timeLeft === 0) {
            onTimeUp();
            reset();
        }
        return () => clearInterval(timerRef.current);
    }, [isActive, timeLeft]);

    return { timeLeft, start, reset, isActive };
}