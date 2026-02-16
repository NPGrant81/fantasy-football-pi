import { useState, useRef, useEffect, useCallback } from 'react';

export function useDraftTimer(initialTime = 10, onTimeUp) {
    const [timeLeft, setTimeLeft] = useState(initialTime);
    const [isActive, setIsActive] = useState(false);
    const timerRef = useRef(null);

    // 1.1 Use useCallback for stable function references
    const reset = useCallback(() => {
        setIsActive(false);
        setTimeLeft(initialTime);
        if (timerRef.current) clearInterval(timerRef.current);
    }, [initialTime]);

    const start = () => setIsActive(true);

    useEffect(() => {
        if (isActive && timeLeft > 0) {
            timerRef.current = setInterval(() => {
                setTimeLeft(prev => {
                    // 1.2 Handle "Time Up" logic inside the functional update
                    if (prev <= 1) {
                        clearInterval(timerRef.current);
                        setIsActive(false);
                        onTimeUp(); // Trigger the callback
                        return 0;
                    }
                    return prev - 1;
                });
            }, 1000);
        }

        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [isActive, onTimeUp]); // 1.3 Removed 'timeLeft' to prevent cascading renders

    return { timeLeft, start, reset, isActive };
}