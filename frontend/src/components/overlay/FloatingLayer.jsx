/* ignore-breakpoints */
import { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { layerDropdown } from '@utils/uiStandards';

export default function FloatingLayer({
  anchorRef,
  open,
  children,
  className = '',
  offset = 8,
  matchWidth = true,
  viewportPadding = 12,
  flip = true,
  shift = true,
  constrainHeight = true,
}) {
  const [positionStyle, setPositionStyle] = useState(null);

  const updatePosition = useCallback(() => {
    if (!open || !anchorRef?.current) {
      return;
    }

    const rect = anchorRef.current.getBoundingClientRect();

    // Start in the default "below anchor" position.
    let top = rect.bottom + offset;
    let bottom;
    let left = rect.left;
    const width = matchWidth ? rect.width : undefined;
    let shouldFlip = false;

    // Optional flip if the menu would run out of room below the anchor.
    if (flip && rect.bottom + offset >= window.innerHeight - viewportPadding) {
      shouldFlip = true;
      top = undefined;
      bottom = Math.max(viewportPadding, window.innerHeight - rect.top + offset);
    }

    // Optional shift to keep the layer inside viewport bounds.
    if (shift && width) {
      const maxLeft = window.innerWidth - viewportPadding - width;
      left = Math.min(Math.max(left, viewportPadding), Math.max(viewportPadding, maxLeft));
    } else if (shift) {
      left = Math.min(
        Math.max(left, viewportPadding),
        Math.max(viewportPadding, window.innerWidth - viewportPadding)
      );
    }

    const maxHeight = constrainHeight
      ? shouldFlip
        ? Math.max(120, rect.top - offset - viewportPadding)
        : Math.max(120, window.innerHeight - top - viewportPadding)
      : undefined;

    setPositionStyle({
      position: 'fixed',
      top,
      bottom,
      left,
      width,
      maxHeight,
    });
  }, [
    anchorRef,
    constrainHeight,
    flip,
    matchWidth,
    offset,
    open,
    shift,
    viewportPadding,
  ]);

  useLayoutEffect(() => {
    const frame = window.requestAnimationFrame(updatePosition);
    return () => window.cancelAnimationFrame(frame);
  }, [updatePosition]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const frame = window.requestAnimationFrame(updatePosition);
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);

    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open, updatePosition]);

  if (!open || !positionStyle) {
    return null;
  }

  return createPortal(
    <div className={`${layerDropdown} ${className}`.trim()} style={positionStyle}>
      {children}
    </div>,
    document.body
  );
}
