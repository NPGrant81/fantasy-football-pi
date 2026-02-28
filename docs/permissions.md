# 🛡️ Role-Based Access Control (RBAC) & Capability Map

This document outlines the permission levels for the **Fantasy Football Pi** platform. It defines what actions each user role can perform within the application.

## 👥 The Roles

1.  **User (Owner):** A standard participant. Controls only their specific team.
2.  **Commissioner:** The manager of a specific League. Has "God Mode" over the draft and league settings, but cannot affect other leagues.
3.  **Site Admin:** The superuser. Has "Root Access" to the entire platform, including server management and creating new leagues.

---

## 🔑 Capability Matrix

### Legend

- ✅ = **Allowed**
- ❌ = **Restricted**
- ⚠️ = **Conditional** (e.g., only their own team)

### 1. General Access & Authentication

| Feature               |     User      | Commissioner  |  Site Admin  | Notes                                                         |
| :-------------------- | :-----------: | :-----------: | :----------: | :------------------------------------------------------------ |
| **Login**             |  Email/Pass   |  Email/Pass   |  Email/Pass  | **Strict:** No public registration. Accounts are invite-only. |
| **Reset Password**    | Contact Admin | Contact Admin | Self-Service | Users must contact Admin/Commish to reset credentials.        |
| **Edit User Profile** |      ✅       |      ✅       |      ✅      | Change Name, Team Name, Team Logo/Icon.                       |
| **View Dashboard**    |      ✅       |      ✅       |      ✅      | Standard view.                                                |

### 2. League Administration

| Feature                | User | Commissioner | Site Admin | Notes                                                  |
| :--------------------- | :--: | :----------: | :--------: | :----------------------------------------------------- |
| **Create New League**  |  ❌  |      ❌      |     ✅     | Only Admin can spawn new league instances.             |
| **Delete League**      |  ❌  |      ❌      |     ✅     | The "Nuclear Option".                                  |
| **Change League Name** |  ❌  |      ✅      |     ✅     |                                                        |
| **Invite/Add Users**   |  ❌  |      ✅      |     ✅     | Commish manages their own player pool.                 |
| **Remove/Kick Users**  |  ❌  |      ✅      |     ✅     |                                                        |
| **Promote to Commish** |  ❌  |      ❌      |     ✅     | Only Admin can grant Commissioner status.              |
| **Create Divisions**   |  ❌  |      ✅      |     ✅     | Create "North/South" divisions for playoff bracketing. |

### 3. The Draft (Auction Engine)

| Feature                | User | Commissioner | Site Admin | Notes                                                       |
| :--------------------- | :--: | :----------: | :--------: | :---------------------------------------------------------- |
| **Start Draft**        |  ❌  |      ✅      |     ✅     | Activates the draft room.                                   |
| **Pause/Resume Draft** |  ❌  |      ✅      |     ✅     | Stops the timer/process.                                    |
| **Start Timer**        |  ❌  |      ✅      |     ✅     | Manually triggers the countdown.                            |
| **Nominate Player**    |  ✅  |      ✅      |     ✅     | Users nominate in turn order; Commish can force-nominate.   |
| **Place Bid**          |  ✅  |      ✅      |     ✅     |                                                             |
| **Undo/Revert Pick**   |  ❌  |      ✅      |     ✅     | "Rollback" feature for accidental clicks.                   |
| **Force Pick**         |  ❌  |      ✅      |     ✅     | Assign a player to a specific team (e.g., connection lost). |
| **End Draft**          |  ❌  |      ✅      |     ✅     | Finalizes rosters and moves to "In-Season" mode.            |

### 4. Roster & Team Management

| Feature                |     User      | Commissioner  |  Site Admin   | Notes                                            |
| :--------------------- | :-----------: | :-----------: | :-----------: | :----------------------------------------------- |
| **Set Lineup**         | ⚠️ (Own Team) | ✅ (Any Team) | ✅ (Any Team) | Commish can set lineups for absentee owners.     |
| **Add/Drop Player**    | ⚠️ (Own Team) | ✅ (Any Team) | ✅ (Any Team) | Subject to Waiver Rules.                         |
| **Trade Players**      |      ✅       |  ✅ (Force)   |  ✅ (Force)   | Users propose; Commish can force-process trades. |
| **Edit Roster Limits** |      ❌       |      ✅       |      ✅       | E.g., Changing Bench size.                       |

### 5. Scoring & Settings

| Feature                | User | Commissioner | Site Admin | Notes                                               |
| :--------------------- | :--: | :----------: | :--------: | :-------------------------------------------------- |
| **Edit Scoring Rules** |  ❌  |      ✅      |     ✅     | Setup points for TDs, Yards, Bonuses.               |
| **Edit Waiver Rules**  |  ❌  |      ✅      |     ✅     | Set priority order, budget (FAAB), or claim limits. |
| **Recalculate Scores** |  ❌  |      ✅      |     ✅     | Re-run scoring engine if a stat correction occurs.  |

### 6. System & Testing

| Feature                   | User | Commissioner | Site Admin | Notes                                        |
| :------------------------ | :--: | :----------: | :--------: | :------------------------------------------- |
| **Create Sandbox**        |  ❌  |      ❌      |     ✅     | Spawns a dummy league with bots for testing. |
| **View Server Logs**      |  ❌  |      ❌      |     ✅     | Access to backend errors and access logs.    |
| **Run "Nuclear" Scripts** |  ❌  |      ❌      |     ✅     | `init_league.py`, `seed_draft.py`, etc.      |

---

## 🧪 Testing Protocols

### Sandbox Environment

- **Goal:** Allow Site Admin to test features without impacting the active "Post Pacific League".
- **Setup:** Admin runs `python create_sandbox.py`.
- **Isolation:** Sandbox data is stored in a separate SQLite file (e.g., `sandbox.db`) or distinct League ID to prevent data bleed.

### User Acceptance Testing (UAT)

Before major features (like the Draft) go live, the Site Admin will perform the following scripts:

1.  **Draft Flow:** Simulate a full 12-team auction with at least 1 user disconnection scenario.
2.  **Scoring Check:** Verify complex scoring (e.g., 40+ yard TD bonus) calculates correctly against known NFL data.
3.  **Permission Check:** Log in as "User" and attempt to access Commissioner settings (Must Fail).
