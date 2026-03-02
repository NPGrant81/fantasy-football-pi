// frontend/src/components/TeamLogo.jsx
import { useState } from 'react';
import PropTypes from 'prop-types';

/**
 * Helmet SVG Icon Component
 * Displays a generic helmet with team colors
 */
const HelmetIcon = ({ primaryColor, secondaryColor, size }) => {
  const iconSizes = {
    sm: 16,
    md: 24,
    lg: 32,
    xl: 40,
  };

  return (
    <svg
      width={iconSizes[size]}
      height={iconSizes[size]}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="opacity-80"
    >
      <path
        d="M12 2C7.58 2 4 5.58 4 10C4 12.5 5.23 14.71 7.12 16.06L8 21H16L16.88 16.06C18.77 14.71 20 12.5 20 10C20 5.58 16.42 2 12 2Z"
        fill={primaryColor}
        stroke={secondaryColor}
        strokeWidth="1.5"
      />
      <path
        d="M9 11C9 11 9.5 12 10.5 12C11.5 12 12 11 12 11"
        stroke={secondaryColor}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <circle cx="9" cy="9" r="1" fill={secondaryColor} />
    </svg>
  );
};

HelmetIcon.propTypes = {
  primaryColor: PropTypes.string.isRequired,
  secondaryColor: PropTypes.string.isRequired,
  size: PropTypes.string.isRequired,
};

/**
 * TeamLogo Component
 * 
 * Displays team logo with fallback to colored helmet icon or initials
 * 
 * @param {Object} teamInfo - Team information object
 * @param {string} teamInfo.logo_url - URL to team logo image
 * @param {string} teamInfo.name - Team name (username)
 * @param {string} teamInfo.team_name - Custom team name
 * @param {string} teamInfo.color_primary - Primary team color (hex)
 * @param {string} teamInfo.color_secondary - Secondary team color (hex)
 * @param {string} size - Size preset: 'sm', 'md', 'lg', 'xl'
 * @param {string} className - Additional CSS classes
 * @param {boolean} showBorder - Show border with team colors
 */
export default function TeamLogo({ 
  teamInfo, 
  size = 'md', 
  className = '',
  showBorder = true 
}) {
  const [imageError, setImageError] = useState(false);

  // Size mappings
  const sizeClasses = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-12 h-12 text-sm',
    lg: 'w-16 h-16 text-base',
    xl: 'w-20 h-20 text-lg',
  };

  // Extract colors with fallbacks
  const primaryColor = teamInfo?.color_primary || '#3b82f6';
  const secondaryColor = teamInfo?.color_secondary || '#1e40af';
  
  // Get display name
  const displayName = teamInfo?.team_name || teamInfo?.name || 'Team';

  // Check if we have a valid logo URL and haven't encountered an error
  const hasValidLogo = teamInfo?.logo_url && !imageError;

  // Border styles
  const borderStyle = showBorder
    ? {
        borderWidth: '2px',
        borderStyle: 'solid',
        borderColor: primaryColor,
      }
    : {};

  return (
    <div
      className={`${sizeClasses[size]} rounded-full flex items-center justify-center overflow-hidden ${className}`}
      style={{
        ...borderStyle,
        backgroundColor: hasValidLogo ? 'transparent' : primaryColor,
      }}
      title={displayName}
    >
      {hasValidLogo ? (
        <img
          src={teamInfo.logo_url}
          alt={`${displayName} logo`}
          className="w-full h-full object-cover"
          onError={() => setImageError(true)}
        />
      ) : (
        <div className="flex items-center justify-center w-full h-full">
          {/* Show helmet icon by default */}
          <HelmetIcon 
            primaryColor={primaryColor} 
            secondaryColor={secondaryColor} 
            size={size} 
          />
        </div>
      )}
    </div>
  );
}

TeamLogo.propTypes = {
  teamInfo: PropTypes.shape({
    logo_url: PropTypes.string,
    name: PropTypes.string,
    team_name: PropTypes.string,
    color_primary: PropTypes.string,
    color_secondary: PropTypes.string,
  }).isRequired,
  size: PropTypes.oneOf(['sm', 'md', 'lg', 'xl']),
  className: PropTypes.string,
  showBorder: PropTypes.bool,
};
