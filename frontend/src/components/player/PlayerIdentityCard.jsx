/* ignore-breakpoints: card uses fixed styling from uiStandards; responsive behaviour is provided by the parent layout */
import { useMemo, useState } from 'react';
import { FiUser } from 'react-icons/fi';
import TeamLogo from '../TeamLogo';

function buildDefenseLogoUrl(nflTeam) {
  const normalized = String(nflTeam || '').trim().toUpperCase();
  if (!normalized) return '';

  const legacyAliases = {
    JAC: 'JAX',
    OAK: 'LV',
    SD: 'LAC',
    STL: 'LAR',
    WSH: 'WAS',
  };
  const canonical = legacyAliases[normalized] || normalized;
  return `https://static.www.nfl.com/t_q-best/league/api/clubs/logos/${canonical}.png`;
}

export default function PlayerIdentityCard({
  title,
  playerName = '',
  position = '',
  nflTeam = '',
  headshotUrl = '',
  teamLogoUrl = '',
}) {
  const [imageFailed, setImageFailed] = useState(false);

  const { firstName, lastName } = useMemo(() => {
    const name = String(playerName || '').trim();
    if (!name) return { firstName: 'Player', lastName: 'Profile' };
    const parts = name.split(/\s+/);
    if (parts.length === 1) {
      return { firstName: parts[0], lastName: '' };
    }
    return {
      firstName: parts.slice(0, -1).join(' '),
      lastName: parts[parts.length - 1],
    };
  }, [playerName]);

  const canShowImage = Boolean(headshotUrl && !imageFailed);
  const isDefense = useMemo(() => {
    const normalized = String(position || '').trim().toUpperCase();
    return normalized === 'DEF' || normalized === 'DST' || normalized === 'D/ST';
  }, [position]);
  const canShowDefenseLogo = isDefense && Boolean(nflTeam);
  const defenseLogoUrl = useMemo(() => {
    if (!canShowDefenseLogo) return '';
    return teamLogoUrl || buildDefenseLogoUrl(nflTeam);
  }, [canShowDefenseLogo, nflTeam, teamLogoUrl]);

  return (
    <div className="mb-4 rounded-xl border border-slate-300 bg-white/80 p-3 dark:border-slate-700 dark:bg-slate-900/70">
      {title ? (
        <div className="mb-2 text-right text-xs font-black uppercase tracking-wider text-slate-500 dark:text-slate-400">
          {title}
        </div>
      ) : null}

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-[3.5rem] pt-1 text-left">
          <div className="text-4xl font-black leading-none tracking-tight text-blue-400">
            {position || '—'}
          </div>
        </div>

        <div className="min-w-0 flex-1 text-right">
          <div className="truncate text-[10px] font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Season Performance
            {(position || nflTeam) && (
              <span>
                {' '}
                {position || 'N/A'}
                {nflTeam ? ` • ${nflTeam}` : ''}
              </span>
            )}
          </div>
          <div className="truncate text-base font-bold text-slate-700 dark:text-slate-300">
            {firstName}
          </div>
          <div className="truncate text-4xl font-black leading-tight tracking-tight text-slate-900 dark:text-white">
            {lastName || firstName}
          </div>
        </div>

        <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-300 bg-slate-100 dark:border-slate-700 dark:bg-slate-950">
          {canShowImage ? (
            <img
              src={headshotUrl}
              alt={`${playerName || 'Player'} headshot`}
              className="h-full w-full object-cover"
              onError={() => setImageFailed(true)}
            />
          ) : canShowDefenseLogo ? (
            <TeamLogo
              teamInfo={{
                logo_url: defenseLogoUrl || null,
                team_name: `${nflTeam} Defense`,
                name: `${nflTeam} Defense`,
              }}
              size="xl"
              className="h-full w-full"
              showBorder={false}
            />
          ) : (
            <FiUser className="text-3xl text-slate-500 dark:text-slate-400" />
          )}
        </div>
      </div>
    </div>
  );
}
