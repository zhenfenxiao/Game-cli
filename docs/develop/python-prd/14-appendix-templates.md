# 14 — Appendix: Game Archetype Templates

This document describes the on-disk template structure that the agent copies to scaffold game projects. These are TypeScript/Phaser game templates, not Python code.

## 14.1 Core Template (M0)

The core template provides the universal foundation shared by all game types.

### Directory Structure

```
templates/core/
├── index.html              # HTML entry point
├── package.json            # NPM dependencies
├── vite.config.js          # Vite build config
├── tsconfig.json           # TypeScript config
├── tailwind.config.js      # Tailwind CSS config
├── postcss.config.js       # PostCSS config
├── README.md               # Project readme
├── src/
│   ├── main.ts             # Scene registration + game init
│   ├── LevelManager.ts     # Level progression manager
│   ├── StateMachine.ts     # Game state machine
│   ├── gameConfig.json     # Configuration schema
│   ├── utils.ts            # Shared utilities
│   ├── styles/
│   │   └── tailwind.css    # Tailwind entry
│   ├── scenes/
│   │   ├── Preloader.ts    # Asset preloading scene
│   │   ├── TitleScreen.ts  # Title/menu scene
│   │   ├── UIScene.ts      # In-game UI overlay
│   │   ├── PauseUIScene.ts # Pause menu
│   │   ├── GameOverUIScene.ts
│   │   ├── GameCompleteUIScene.ts
│   │   └── VictoryUIScene.ts
│   └── test/
│       ├── setup.ts        # Test setup
│       └── helpers/
│           └── phaser.ts   # Phaser test helpers
```

### Key Files

**main.ts**: Registers all scenes and initializes the Phaser game instance.

```typescript
import { Game, Types } from 'phaser';
// Scene imports... (auto-populated during Phase 4)

const config: Types.Core.GameConfig = {
  type: Phaser.AUTO,
  width: 1280,
  height: 720,
  parent: 'game-container',
  backgroundColor: '#000000',
  scene: [
    Preloader,
    TitleScreen,
    // Game scenes added here during scaffolding
  ],
  physics: {
    default: 'arcade',
    arcade: {
      gravity: { x: 0, y: 0 },
      debug: false,
    },
  },
};

export default new Game(config);
```

**LevelManager.ts**: Manages level progression and scene transitions.

```typescript
export class LevelManager {
  static LEVEL_ORDER: string[] = ['TitleScreen'];
  static currentLevelIndex = 0;

  static getCurrentLevel(): string {
    return this.LEVEL_ORDER[this.currentLevelIndex];
  }

  static advance(scene: Phaser.Scene): void {
    this.currentLevelIndex++;
    if (this.currentLevelIndex < this.LEVEL_ORDER.length) {
      scene.scene.start(this.getCurrentLevel());
    } else {
      scene.scene.start('VictoryUIScene');
    }
  }

  static restart(scene: Phaser.Scene): void {
    this.currentLevelIndex = 0;
    scene.scene.start(this.getCurrentLevel());
  }
}
```

**gameConfig.json**: Centralized configuration with value wrapper format.

```json
{
  "screenSize": {
    "width": { "value": 1280 },
    "height": { "value": 720 }
  },
  "debugConfig": {
    "showFPS": { "value": false },
    "showHitboxes": { "value": false }
  },
  "renderConfig": {
    "pixelArt": { "value": true },
    "antialias": { "value": false }
  }
}
```

## 14.2 Archetype Modules

Each archetype adds game-specific code into the `src/` directory via additive merge.

### Platformer Module

```
templates/modules/platformer/src/
├── behaviors/
│   ├── BehaviorManager.ts    # Behavior orchestration
│   ├── IBehavior.ts          # Behavior interface
│   ├── PlatformerMovement.ts # Gravity + jump movement
│   ├── PatrolAI.ts           # Enemy patrol behavior
│   ├── ChaseAI.ts            # Enemy chase behavior
│   ├── MeleeAttack.ts        # Melee combat
│   ├── RangedAttack.ts       # Projectile combat
│   ├── SkillBehavior.ts      # Special abilities
│   └── ScreenEffectHelper.ts # Screen shake, flash
├── characters/
│   ├── BasePlayer.ts         # Player base class
│   ├── BaseEnemy.ts          # Enemy base class
│   ├── PlayerFSM.ts          # Player finite state machine
│   ├── _TemplatePlayer.ts    # Copy template for player
│   └── _TemplateEnemy.ts     # Copy template for enemies
├── scenes/
│   ├── BaseLevelScene.ts     # Base level with platforms
│   ├── CharacterSelectScene.ts
│   ├── _TemplateLevel.ts     # Copy template for levels
│   └── UIScene.ts            # Game HUD
└── utils.ts                  # Platformer utilities
```

**Physics Profile**: hasGravity=true, perspective=side, movement=continuous

### Top-Down Module

```
templates/modules/top_down/src/
├── behaviors/
│   ├── EightWayMovement.ts   # 8-directional movement
│   ├── DashAbility.ts        # Dash/dodge mechanic
│   ├── FaceTarget.ts         # Rotation toward target
│   ├── PatrolAI.ts           # Enemy patrol
│   ├── ChaseAI.ts            # Enemy chase
│   ├── MeleeAttack.ts        # Melee combat
│   ├── RangedAttack.ts       # Projectile combat
│   └── ScreenEffectHelper.ts
├── characters/
│   ├── BasePlayer.ts
│   ├── BaseEnemy.ts
│   ├── PlayerFSM.ts
│   ├── _TemplatePlayer.ts
│   └── _TemplateEnemy.ts
├── scenes/
│   ├── BaseArenaScene.ts     # Arena/room base
│   ├── BaseGameScene.ts      # Game world base
│   ├── BaseLevelScene.ts
│   ├── _TemplateArena.ts
│   ├── _TemplateLevel.ts
│   └── UIScene.ts
└── utils.ts
```

**Physics Profile**: hasGravity=false, perspective=top_down, movement=continuous

### Grid Logic Module

```
templates/modules/grid_logic/src/
├── entities/
│   ├── BaseGridEntity.ts     # Grid-positioned entity base
│   ├── _TemplateEntity.ts    # Copy template for entities
│   └── index.ts
├── scenes/
│   ├── BaseGridScene.ts      # Grid-based scene base
│   ├── _TemplateGridLevel.ts # Copy template for levels
│   ├── UIScene.ts
│   └── index.ts
├── systems/
│   ├── BoardManager.ts       # Grid state management
│   ├── TurnManager.ts        # Turn-based flow control
│   ├── AnimationQueue.ts     # Sequential animation player
│   └── index.ts
├── gameConfig.json           # Grid-specific config
└── utils.ts
```

**Physics Profile**: hasGravity=false, perspective=top_down, movement=grid

### Tower Defense Module

```
templates/modules/tower_defense/src/
├── enemies/
│   ├── BaseTDEnemy.ts        # Enemy with path following
│   ├── _TemplateTDEnemy.ts
│   └── index.ts
├── entities/
│   ├── BaseObstacle.ts       # Placeable obstacles
│   ├── _TemplateObstacle.ts
│   └── index.ts
├── towers/
│   ├── BaseTower.ts          # Tower base with range/aim
│   ├── _TemplateTower.ts
│   └── index.ts
├── scenes/
│   ├── BaseTDScene.ts        # TD game scene base
│   ├── _TemplateTDLevel.ts
│   ├── UIScene.ts
│   └── index.ts
├── systems/
│   ├── EconomyManager.ts     # Currency/income system
│   ├── WaveManager.ts        # Enemy wave spawner
│   └── index.ts
├── gameConfig.json
└── utils.ts
```

**Physics Profile**: hasGravity=false, perspective=top_down, movement=path

### UI Heavy Module

```
templates/modules/ui_heavy/src/
├── scenes/
│   ├── BaseBattleScene.ts    # Turn-based battle base
│   ├── BaseChapterScene.ts   # Story chapter base
│   ├── BaseCharacterSelectScene.ts
│   ├── BaseEndingScene.ts
│   ├── ChapterSelectScene.ts
│   ├── _TemplateBattle.ts
│   ├── _TemplateChapter.ts
│   ├── _TemplateCharacterSelect.ts
│   ├── _TemplateDualBattle.ts
│   ├── _TemplateEnding.ts
│   └── index.ts
├── systems/
│   ├── CardManager.ts        # Card deck/hand management
│   ├── ChoiceManager.ts      # Dialogue choice system
│   ├── ComboManager.ts       # Combo/score tracking
│   ├── DialogueManager.ts    # Dialogue tree player
│   ├── DualPlayerSystem.ts   # 2-player mode
│   ├── GameDataManager.ts    # Save/load progression
│   ├── QuizManager.ts        # Question/answer system
│   ├── TurnManager.ts        # Turn order management
│   └── index.ts
├── ui/
│   ├── Card.ts               # Card UI component
│   ├── CharacterPortrait.ts  # Character display
│   ├── ChoicePanel.ts        # Choice buttons
│   ├── DialogueBox.ts        # Dialogue text box
│   ├── FloatingText.ts       # Damage/heal numbers
│   ├── ModalOverlay.ts       # Modal dialog
│   ├── QuizModal.ts          # Quiz interface
│   ├── StatusBar.ts          # HP/MP bars
│   ├── TweenPresets.ts       # Common animations
│   └── index.ts
├── gameConfig.json
└── index.ts
```

**Physics Profile**: hasGravity=false, perspective=none, movement=ui_only

## 14.3 Hook Pattern

All archetypes use the **Hook Pattern** for customization:

### Base Class Lifecycle

```typescript
// Base class handles the full lifecycle
abstract class BaseLevelScene extends Phaser.Scene {
  create(): void {
    // 1. Setup physics
    this.setupPhysics();
    // 2. Load tilemap
    this.loadTilemap();
    // 3. Spawn entities
    this.spawnEntities();
    // 4. Setup camera
    this.setupCamera();
    // 5. Setup UI
    this.setupUI();
    // 6. Call custom hook
    this.onLevelStart();
  }

  update(time: number, delta: number): void {
    // Update all systems
    this.updateEntities(delta);
    // Call custom hook
    this.onUpdate(time, delta);
  }

  // --- Hooks (override these) ---
  protected onLevelStart(): void {}      // Called after setup
  protected onUpdate(time: number, delta: number): void {}
  protected onPlayerDeath(): void {}      // Player died
  protected onLevelComplete(): void {}    // Level finished
}
```

### Custom Scene (COPY from _Template)

```typescript
// COPY from _TemplateLevel.ts, customize hooks
class Level1 extends BaseLevelScene {
  constructor() {
    super({ key: 'Level1' });
  }

  protected override onLevelStart(): void {
    super.onLevelStart();
    // Custom: spawn specific enemies
    this.spawnEnemy('goblin', 500, 200);
  }

  protected override onUpdate(time: number, delta: number): void {
    // Custom: check win condition
    if (this.enemies.countActive() === 0) {
      this.onLevelComplete();
    }
  }
}
```

## 14.4 KEEP Files vs Copy Templates

| File Pattern | Rule | Example |
|-------------|------|---------|
| `Base*.ts` | **KEEP** — never modify | `BasePlayer.ts`, `BaseLevelScene.ts` |
| `Behavior*.ts` | **KEEP** — never modify | `PatrolAI.ts`, `MeleeAttack.ts` |
| `System*.ts` | **KEEP** — never modify | `BoardManager.ts`, `WaveManager.ts` |
| `UI*.ts` | **KEEP** — never modify | `Card.ts`, `DialogueBox.ts` |
| `_Template*.ts` | **COPY** — copy and customize | `_TemplatePlayer.ts` → `MyPlayer.ts` |
| `utils.ts` | **KEEP** — never modify | Shared utilities |

## 14.5 Config Value Wrapper Format

All values in `gameConfig.json` use the wrapper format:

```json
{
  "fieldName": {
    "value": 100,
    "type": "number",
    "description": "What this config does"
  }
}
```

Access in code:
```typescript
const speed = gameConfig.playerSpeed.value;  // 100
const name = gameConfig.gameTitle.value;      // "My Game"
```

This format allows:
- Type validation
- Description for documentation
- Runtime config inspection
- Editor integration

## 14.6 Asset Pack Format

```json
{
  "assets": [
    {
      "key": "player_sprite",
      "type": "image",
      "url": "assets/player.png"
    },
    {
      "key": "enemy_walk",
      "type": "spritesheet",
      "url": "assets/enemy_walk.png",
      "frameWidth": 32,
      "frameHeight": 32
    },
    {
      "key": "bgm_battle",
      "type": "audio",
      "url": "assets/bgm_battle.mp3"
    }
  ]
}
```

Loaded by `Preloader.ts`:
```typescript
preload(): void {
  const pack = this.cache.json.get('asset-pack');
  for (const asset of pack.assets) {
    if (asset.type === 'image') {
      this.load.image(asset.key, asset.url);
    } else if (asset.type === 'spritesheet') {
      this.load.spritesheet(asset.key, asset.url, {
        frameWidth: asset.frameWidth,
        frameHeight: asset.frameHeight,
      });
    } else if (asset.type === 'audio') {
      this.load.audio(asset.key, asset.url);
    }
  }
}
```
