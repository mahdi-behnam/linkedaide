# Changelog

## [1.8.1](https://github.com/mahdi-behnam/linkedaide/compare/v1.8.0...v1.8.1) (2026-10-26)


### Bug Fixes

* **browser:** use wait_for for real Playwright locator availability checks ([b12fa98](https://github.com/mahdi-behnam/linkedaide/commit/b12fa984804679a92e7e0fe78a5b865903662ecb))

## [1.8.0](https://github.com/mahdi-behnam/linkedaide/compare/v1.7.2...v1.8.0) (2026-10-19)


### Features

* **ci:** add version-controlled git pre-commit and pre-push quality hooks ([d4a62ab](https://github.com/mahdi-behnam/linkedaide/commit/d4a62ab95f361ba2ccd8daf54d240cec6c4d9530))


### Bug Fixes

* **browser:** ground execution selectors and DOM handlers against live LinkedIn ([4d44638](https://github.com/mahdi-behnam/linkedaide/commit/4d4463815349948b90f9387f81267ccf63d694bd))
* **ci:** fix ruff import sorting, formatting, and mypy return type in browser actions ([060bf79](https://github.com/mahdi-behnam/linkedaide/commit/060bf79d78d130091fa983d63844768a8b8b7949))


### Tests

* **graphs:** update execute reaction test assertion to verify post_url ([8f29ab7](https://github.com/mahdi-behnam/linkedaide/commit/8f29ab70a0855b9ac9d5e5ab43acdbb5fdd994b7))

## [1.7.2](https://github.com/mahdi-behnam/linkedaide/compare/v1.7.1...v1.7.2) (2026-10-18)


### Bug Fixes

* **ci:** resolve python and typescript typecheck, lint, and test errors ([100e310](https://github.com/mahdi-behnam/linkedaide/commit/100e310084e5b47b8164597711d34907de4272ac))
* **execute:** fix session verification navigation and reaction handling ([76653ce](https://github.com/mahdi-behnam/linkedaide/commit/76653ce157220483e1331fdab6fcaf0f97b28053))
* **tests:** supply required settings and mock loader in isolated test environments ([6d8a54f](https://github.com/mahdi-behnam/linkedaide/commit/6d8a54fcef41f373da953d5ccfaf3c86c1ad8e41))

## [1.7.1](https://github.com/mahdi-behnam/linkedaide/compare/v1.7.0...v1.7.1) (2026-10-16)


### Bug Fixes

* **desktop:** resolve typescript compiler errors for deep navigation and search ([aa19732](https://github.com/mahdi-behnam/linkedaide/commit/aa19732d055150bd174734ec5f489eb190f8f829))

## [1.7.0](https://github.com/mahdi-behnam/linkedaide/compare/v1.6.0...v1.7.0) (2026-10-16)


### Features

* **desktop:** add deep navigation target state and dom highlight hook ([0a458a1](https://github.com/mahdi-behnam/linkedaide/commit/0a458a1d737e71faf42050c307b77e1d674bcde2))
* **desktop:** implement search indexing and relevance scoring service ([8dcdcb2](https://github.com/mahdi-behnam/linkedaide/commit/8dcdcb2e804cca075fd1a4c67962173647637b98))
* **desktop:** integrate deep navigation in settings, queue, outreach, and history views ([2edb526](https://github.com/mahdi-behnam/linkedaide/commit/2edb526b8123b72ca1ec21a1eff8f5b86f01429c))
* **desktop:** upgrade command palette with universal search and deep navigation ([1a25942](https://github.com/mahdi-behnam/linkedaide/commit/1a25942459560932577340d67ed102d484f58fb7))


### Bug Fixes

* **desktop:** render rich HTML in update release notes and increase popover height ([2780c4f](https://github.com/mahdi-behnam/linkedaide/commit/2780c4f7749c3caeb06b49c2fdcabf2257fddfa2))

## [1.6.0](https://github.com/mahdi-behnam/linkedaide/compare/v1.5.0...v1.6.0) (2026-10-16)


### Features

* **desktop:** add fork drift detection and document 1-click sync ([2f4d39d](https://github.com/mahdi-behnam/linkedaide/commit/2f4d39d13b82ce72678f2778aff33a0bb208648a))
* **safety:** prepare repository and desktop app for public release ([d8ba5b6](https://github.com/mahdi-behnam/linkedaide/commit/d8ba5b6db8e917a03bf49d391ddcc543eed3249d))

## [1.5.0](https://github.com/mahdi-behnam/linkedaide/compare/v1.4.3...v1.5.0) (2026-10-16)


### Features

* **analytics:** replace fabricated reach and engagement formulas with real execution telemetry ([9290d7f](https://github.com/mahdi-behnam/linkedaide/commit/9290d7f7d35427ba5c3d523fc28fd5a98cd0629b))
* **calendar:** connect safeguards card to real quota and add pillar editorial guidelines ([06622a1](https://github.com/mahdi-behnam/linkedaide/commit/06622a1a6d6a663c3aff0e1623fc0f6115c46f75))
* **dashboard:** replace simulated dispatcher charts and mock queue with live telemetry ([8a34785](https://github.com/mahdi-behnam/linkedaide/commit/8a347851368c5dfd3788a2c0a2bfd06d626209db))


### Bug Fixes

* **doctor:** eliminate mock secrets and fake telemetry metrics ([02845b9](https://github.com/mahdi-behnam/linkedaide/commit/02845b946ad96eb0f1228d559e58093e228a20c9))
* **vault:** remove fabricated fingerprint, mock blob sizes, and simulated PoPs ([a14e14c](https://github.com/mahdi-behnam/linkedaide/commit/a14e14c0afd7f2f01c1b9b5dc958868d4d88ee2b))

## [1.4.3](https://github.com/mahdi-behnam/linkedaide/compare/v1.4.2...v1.4.3) (2026-10-16)


### Bug Fixes

* **ci:** track desktop build icon assets and synchronize during packaging ([cb2bd27](https://github.com/mahdi-behnam/linkedaide/commit/cb2bd2773f768db78eb2d9739be4d6314bbf4c4d))

## [1.4.2](https://github.com/mahdi-behnam/linkedaide/compare/v1.4.1...v1.4.2) (2026-10-16)


### Code Refactoring

* replace remaining linkedin-hitl-agent references with linkedaide ([bc6c017](https://github.com/mahdi-behnam/linkedaide/commit/bc6c0171acf6d44186172594cfabaf63ae783be7))

## [1.4.1](https://github.com/mahdi-behnam/linkedaide/compare/v1.4.0...v1.4.1) (2026-10-16)


### Bug Fixes

* **desktop:** resolve application, desktop shortcut, and taskbar icons ([befb4d9](https://github.com/mahdi-behnam/linkedaide/commit/befb4d91593d99f7abc1f393f2b488f07db8a82e))

## [1.4.0](https://github.com/mahdi-behnam/linkedaide/compare/v1.3.0...v1.4.0) (2026-10-16)


### Features

* **desktop:** add electron-updater and IPC type contracts for auto-updates ([bd36f04](https://github.com/mahdi-behnam/linkedaide/commit/bd36f04e6df1304cf27d11819de0ef125ad1f9f0))
* **desktop:** create Apple HIG UpdatePill and UpdatePopover UI components ([fe68a45](https://github.com/mahdi-behnam/linkedaide/commit/fe68a45db5f86634d96b91ddf7356d9c5563de5f))
* **desktop:** implement UpdateManager with startup check and progress tracking ([c2429cd](https://github.com/mahdi-behnam/linkedaide/commit/c2429cdfaca913e6f8d69d2e15ea968c117bf81f))


### Tests

* **desktop:** add unit and component tests for update lifecycle and UI ([aa0c6c0](https://github.com/mahdi-behnam/linkedaide/commit/aa0c6c0e1dcb3d9b109a6c8deebdac9bc50a2415))

## [1.3.0](https://github.com/mahdi-behnam/linkedaide/compare/v1.2.1...v1.3.0) (2026-10-16)

### Features

- **browser:** decode protobuf activity tokens in modern feed cards ([4abe176](https://github.com/mahdi-behnam/linkedaide/commit/4abe176c541a66c7e002523658421a8acb46ff42))

### Bug Fixes

- **browser:** resolve real post URNs from expanded containers and prevent invalid links ([5e17b1a](https://github.com/mahdi-behnam/linkedaide/commit/5e17b1aee89d9d0a2e47677e065512da5fdebced))

## [1.2.1](https://github.com/mahdi-behnam/linkedaide/compare/v1.2.0...v1.2.1) (2026-10-15)

### Bug Fixes

- **ci:** automatically publish release and set latest tag ([fbaeba9](https://github.com/mahdi-behnam/linkedaide/commit/fbaeba9a63cfc2ffd5d1efe60e5b16c3a0590796))

## [1.2.0](https://github.com/mahdi-behnam/linkedaide/compare/v1.1.0...v1.2.0) (2026-10-15)

### Features

- **browser:** add organic pre-comment reaction simulation and humanized dwell timing ([faa9068](https://github.com/mahdi-behnam/linkedaide/commit/faa90685422770d696f6777fba26e6945a44d9c4))
- **browser:** add Playwright session and actions ([1d9c3ec](https://github.com/mahdi-behnam/linkedaide/commit/1d9c3ec811555b329de6b22c39b9420909788cac))
- **browser:** add targeted scouting for hashtags and custom feeds ([b9f8228](https://github.com/mahdi-behnam/linkedaide/commit/b9f822836c94e4b1f4a7f78854b8e1317ac00b7b))
- **browser:** extract author profile url directly from feed cards ([baae33c](https://github.com/mahdi-behnam/linkedaide/commit/baae33c1e9d0ba1b58d404bc99f444ed17689410))
- **browser:** implement 4-tier self-healing selectors and residential proxy gateway ([19c3df7](https://github.com/mahdi-behnam/linkedaide/commit/19c3df7f979da670f1b0968370b6c593606350ff))
- **browser:** implement active post-submission DOM verification and error capture ([e8a0271](https://github.com/mahdi-behnam/linkedaide/commit/e8a02711a3e351537aa714143ca087370b5c376e))
- **browser:** implement behavioral biometrics and rolling cookie keepalive ([a43d9a5](https://github.com/mahdi-behnam/linkedaide/commit/a43d9a5a910e51f2fef6b8ade50f98015babd8e6))
- **browser:** implement sanitized DOM telemetry and selector drift diagnostics ([3d87d7d](https://github.com/mahdi-behnam/linkedaide/commit/3d87d7dacd2444707825346a0de92d245ade49e7))
- **browser:** modernize DOM selectors, auto-decrypt sessions, and add file logging ([e7c48d8](https://github.com/mahdi-behnam/linkedaide/commit/e7c48d8b6fa1cce270d13cc5687ba8606bdf66c6))
- **browser:** support downloading remote r2 media assets for scheduled post submissions ([bcae442](https://github.com/mahdi-behnam/linkedaide/commit/bcae442702c2d97d3696e12f61949359e3ebd11c))
- **browser:** wire self-healing selector engine into action executor mixins ([a4b6f1e](https://github.com/mahdi-behnam/linkedaide/commit/a4b6f1e28e04fd606625b2a838b60643b9b81336))
- **ci:** automate desktop release pipeline and add download badges to README ([0d94be7](https://github.com/mahdi-behnam/linkedaide/commit/0d94be7326239f43a1c403cf8956523d051bb317))
- **cli:** add dedicated connection outreach command ([e481b00](https://github.com/mahdi-behnam/linkedaide/commit/e481b0034b367556ea6133c8304120e2ed7fe955))
- **cli:** add DESKTOP_API_SECRET automated generation to scripts, setup wizard, and docs ([ce90f86](https://github.com/mahdi-behnam/linkedaide/commit/ce90f86188fcb2beea605681ec3507253d1dc1c6))
- **cli:** add package main entrypoint and register all subcommands ([226d666](https://github.com/mahdi-behnam/linkedaide/commit/226d66649d1d6cd2356549a92582039a9748e6c3))
- **cli:** add targeted connection outreach scout command ([d1ca693](https://github.com/mahdi-behnam/linkedaide/commit/d1ca693988af9eaa27f6191bc1878e85db725699))
- **cli:** add unified cli with interactive setup wizard and doctor diagnostics ([739d462](https://github.com/mahdi-behnam/linkedaide/commit/739d462fc96d095332d11076a50009ba3ee637f2))
- **composer:** implement 2-pane Post Composer Studio and Content Calendar ([a3cc3ea](https://github.com/mahdi-behnam/linkedaide/commit/a3cc3eada82a476f3262fbfa97fb9d0c8806ef34))
- **dashboard:** align Command Center and Growth Analytics with Serene Craft design ([5695355](https://github.com/mahdi-behnam/linkedaide/commit/569535512b61862e0b16325b701f846560f02211))
- **desktop:** add ⌘k command palette and tab navigation history ([3253088](https://github.com/mahdi-behnam/linkedaide/commit/32530888cc04d8a4c75ba8cb41e895aafb817f34))
- **desktop:** add application-wide timezone configuration and formatting ([0f6b6b1](https://github.com/mahdi-behnam/linkedaide/commit/0f6b6b1fde307ef339261f0e07409421fa434d81))
- **desktop:** add daily connection outreach limit to safety settings and align counters ([ae7fa45](https://github.com/mahdi-behnam/linkedaide/commit/ae7fa455d4e6671ab66645a1aaebfb9d6813bc6b))
- **desktop:** add durable r2 media upload bridge for post composer studio ([5d847d6](https://github.com/mahdi-behnam/linkedaide/commit/5d847d66996a6e236458dd818bf9ea16224870d4))
- **desktop:** add dynamic NVIDIA NIM model selector with live catalog fetching ([9cdc06b](https://github.com/mahdi-behnam/linkedaide/commit/9cdc06bfc9904367d215d71cc4796c31b7902db2))
- **desktop:** add floating unsaved changes dock and navigation lock modal in settings ([55e2301](https://github.com/mahdi-behnam/linkedaide/commit/55e23018ffe1b750fd11db4d3bec3e4130accf83))
- **desktop:** add scout targeting and engine parameters to settings ([a3e3e5d](https://github.com/mahdi-behnam/linkedaide/commit/a3e3e5da9c55dae516d1d904e29e7a109e33394f))
- **desktop:** add self-healing electron prestart script and automated multi-platform release workflow ([e8e8ef2](https://github.com/mahdi-behnam/linkedaide/commit/e8e8ef2f64f3b7df24e5d1a47c8da624a3e27fa4))
- **desktop:** build linear-style component system and navigation layout ([382bd36](https://github.com/mahdi-behnam/linkedaide/commit/382bd3666229d1875331ab170dbc117c38eba010))
- **desktop:** build linear-style component system and navigation layout ([e89c972](https://github.com/mahdi-behnam/linkedaide/commit/e89c972a1f68688931bbb2b58d5993aeb4a4f783))
- **desktop:** configure github cloud runner credentials and audit diagnostics ([05d1780](https://github.com/mahdi-behnam/linkedaide/commit/05d1780f738cf52bde30c71030cfbfdfc0268d9d))
- **desktop:** declare session vault IPC contracts ([45e3572](https://github.com/mahdi-behnam/linkedaide/commit/45e3572975610a0e3c47f82da2869c61b367058c))
- **desktop:** dynamically bind auto-polling interval in approval queue status bar ([25a9fef](https://github.com/mahdi-behnam/linkedaide/commit/25a9fefa1c548b890f730680f33126e0dfd5937b))
- **desktop:** enable executing agent doctor diagnostic suite from desktop ([82a114c](https://github.com/mahdi-behnam/linkedaide/commit/82a114c7b0ce0406267cf5e1b8a69240ad764cef))
- **desktop:** expand audit history action types and filtering ([80596ca](https://github.com/mahdi-behnam/linkedaide/commit/80596ca8c7a8f5bb54c8463b1ec6b9c1f73e6bce))
- **desktop:** implement approval queue with ai tone rewriting studio ([51ca2e5](https://github.com/mahdi-behnam/linkedaide/commit/51ca2e5bb5164c2cd9cab6239fab1ec87d03f5fa))
- **desktop:** implement configurable scout schedule management in UI and bridge ([bfd6e5e](https://github.com/mahdi-behnam/linkedaide/commit/bfd6e5e79e03404d0b7d32e927123d3cf7af8fd1))
- **desktop:** implement electron main process secure ipc and fernet crypto ([aab4db7](https://github.com/mahdi-behnam/linkedaide/commit/aab4db7b3a59b3cf458080e9fb6f4de1477acfeb))
- **desktop:** implement electron main process secure ipc and fernet crypto ([246028f](https://github.com/mahdi-behnam/linkedaide/commit/246028fe253281b17f5e520669ac521fa9be9449))
- **desktop:** implement hidden title bar with window controls overlay ([9c04ff5](https://github.com/mahdi-behnam/linkedaide/commit/9c04ff5d4a25e3d8cbea870a7fa05fb876665d92))
- **desktop:** implement interactive dual-mode settings and local runner execution ([205f40e](https://github.com/mahdi-behnam/linkedaide/commit/205f40ec56f8a2dd16365fff6371504a74c0d92a))
- **desktop:** implement linkedin session vault and embedded auth ([ca7d9fb](https://github.com/mahdi-behnam/linkedaide/commit/ca7d9fbc7ffe008eaebdc6718bb4c3c2516a68a0))
- **desktop:** implement post composer studio and visual calendar planner ([1cb9294](https://github.com/mahdi-behnam/linkedaide/commit/1cb9294c388236651ead94f19d7bd8ede3e80c21))
- **desktop:** implement power user keyboard shortcuts and cheat sheet overlay ([4f02f5c](https://github.com/mahdi-behnam/linkedaide/commit/4f02f5c926c4e6a14cbc4cbdb253943076422f1a))
- **desktop:** implement system tray and background notification engine ([05ece9a](https://github.com/mahdi-behnam/linkedaide/commit/05ece9a550f748760ea2f4178e616591443c2aec))
- **desktop:** implement voice audio dictation and linkedin growth analytics dashboard ([8be0e28](https://github.com/mahdi-behnam/linkedaide/commit/8be0e2877455714b7420988ecc16b9781caa104d))
- **desktop:** integrate LinkedAide branding, dynamic status icons, and tray assets ([d6944c2](https://github.com/mahdi-behnam/linkedaide/commit/d6944c228f935a9b8c7ae2a223615f055a24a0a4))
- **desktop:** integrate post scheduling, outreach queue, and worker relay endpoints ([4486539](https://github.com/mahdi-behnam/linkedaide/commit/4486539b4b85fb008c630b2ffe0e66fb46abcc53))
- **desktop:** populate and synchronize default automated scout comment windows ([915db03](https://github.com/mahdi-behnam/linkedaide/commit/915db0306e521530edc766374d19874160c4c9da))
- **desktop:** propagate headed mode flag to local scout process execution ([634bd8e](https://github.com/mahdi-behnam/linkedaide/commit/634bd8e20fe6fd669882e56b383ac917fcdd7d21))
- **desktop:** refine UI ergonomics, OS shortcuts, and notification system ([2ac6ece](https://github.com/mahdi-behnam/linkedaide/commit/2ac6ece5ad083130afaaabc1a4bdb57e8eb97e49))
- **desktop:** restore native application menu and wire ipc action dispatch ([3424f2f](https://github.com/mahdi-behnam/linkedaide/commit/3424f2f440934097e5c6489c90192a63caa566a2))
- **desktop:** wire post ideation trigger, varied reactions, and thread replies in approval queue ([5124882](https://github.com/mahdi-behnam/linkedaide/commit/51248822365452fcc5302f5daa50f8951a6113fe))
- **docs:** add secret generator script and improve setup guide ([d1f44d1](https://github.com/mahdi-behnam/linkedaide/commit/d1f44d18a42668d3fb6f6a225c9e9c0d76753f21))
- **execute:** add progressive lifecycle updates and direct LinkedIn verification links ([cb8bd93](https://github.com/mahdi-behnam/linkedaide/commit/cb8bd93abb2fce22359ce3fc32b4d23c211910f9))
- **execute:** manage scheduled post lifecycle and support media attachments ([bb652c8](https://github.com/mahdi-behnam/linkedaide/commit/bb652c8f915c47d8b6659362ab7e81d667be5737))
- **graphs:** add LangGraph workflow machines ([283dffc](https://github.com/mahdi-behnam/linkedaide/commit/283dffcd3353ab6b5a98f627651f912a3577632f))
- **graphs:** implement original post ideation graph and workflow ([4b6acb0](https://github.com/mahdi-behnam/linkedaide/commit/4b6acb0d845fc0577eefa556aca3f5be8d2cc235))
- **graphs:** implement thread monitor graph and state machine ([00d2d13](https://github.com/mahdi-behnam/linkedaide/commit/00d2d133670d4b54d14f7095ec8eb39f6ac170c6))
- **graphs:** wire connection outreach, thread monitoring, and execution dispatch ([7455ee0](https://github.com/mahdi-behnam/linkedaide/commit/7455ee0ebeaf4be02622a53861f260753f26f64a))
- **graphs:** wire reaction routing and execution across scout and execute graphs ([96e81f5](https://github.com/mahdi-behnam/linkedaide/commit/96e81f51048cd49e9790b2f33e9f7bd535ebced5))
- **llm:** add multi-provider support for openai, anthropic, gemini, groq, and ollama ([e088647](https://github.com/mahdi-behnam/linkedaide/commit/e0886470e57dcfb6f063713499f73aeff8ce02d8))
- **llm:** add multi-provider support for openai, anthropic, gemini, groq, and ollama ([1f41b6b](https://github.com/mahdi-behnam/linkedaide/commit/1f41b6b3dbb670b657cd7eac8bf3021393fb9987))
- **llm:** add NVIDIA NIM LangChain integration ([12fbe60](https://github.com/mahdi-behnam/linkedaide/commit/12fbe601c5b22cf528380cb9edad8e23f0036511))
- **llm:** enforce anti-cliche guardrails on thread replies and post ideation ([6ad615c](https://github.com/mahdi-behnam/linkedaide/commit/6ad615c1bcc8719df75891ba241e224110196696))
- **llm:** implement multimodal vision analysis and diagram-grounded drafting ([348a751](https://github.com/mahdi-behnam/linkedaide/commit/348a75148a8de82fa6f4a6571c8a74bb00a0c8b5))
- **llm:** implement persona voice vector memory and dynamic few-shot injection ([506ea26](https://github.com/mahdi-behnam/linkedaide/commit/506ea26832979742eaed169c8f305d71003bb4bf))
- **llm:** introduce dynamic engagement styles and contextual prompt adaptation ([16505d8](https://github.com/mahdi-behnam/linkedaide/commit/16505d8993a371be3a78c56605978265763a0058))
- **llm:** support nvidia nim vision models in multimodal extractor ([9b80793](https://github.com/mahdi-behnam/linkedaide/commit/9b80793dd78a28c9fcb94dbb165a248377461421))
- **llm:** wire voice memory continuous learning with durable state persistence ([99deb88](https://github.com/mahdi-behnam/linkedaide/commit/99deb88e0372dcd59cbf2ffd7e84fded55ba772a))
- **models:** add domain schemas and config ([ce420f3](https://github.com/mahdi-behnam/linkedaide/commit/ce420f3c4d488ecac35277e81784b73190046a9d))
- **models:** add reaction types, triage recommendations, and pending action support ([6279d56](https://github.com/mahdi-behnam/linkedaide/commit/6279d56e9beba5bdab02fcd0d76fd8fb80ae9b1d))
- **orchestration:** add process entrypoint flows ([e1e3ae7](https://github.com/mahdi-behnam/linkedaide/commit/e1e3ae7e76382398e24eb5a9b6744b8e8df0088d))
- **orchestration:** implement thread reply monitoring orchestration and cli command ([a5944c1](https://github.com/mahdi-behnam/linkedaide/commit/a5944c176de1c17d37b8572066423e9b00310177))
- **outreach:** implement connection request hitl queue and safety caps ([7d4b640](https://github.com/mahdi-behnam/linkedaide/commit/7d4b64034a36b3db2134d3367065ee245081ba0a))
- **queue:** modernize Approval Queue and Outreach Queue with Things 3 layout ([2749ef1](https://github.com/mahdi-behnam/linkedaide/commit/2749ef1fee78a0c663be0706c79bcd5ff7729d99))
- **r2:** implement cloudflare r2 media vault for audit screenshots and carousel assets ([579ca40](https://github.com/mahdi-behnam/linkedaide/commit/579ca400bdd8a327af4883aba4e4ce3803563082))
- **realtime:** implement cloudflare worker websocket push hub and instant desktop sync ([82616c4](https://github.com/mahdi-behnam/linkedaide/commit/82616c4fba557f048245db015d9e54c8f5c248dd))
- **relay:** add Cloudflare Worker Telegram relay ([ed7dcdc](https://github.com/mahdi-behnam/linkedaide/commit/ed7dcdc939462f53190af907e1113bbc41127128))
- **relay:** add cron trigger and handler for scheduled post dispatch ([aa77483](https://github.com/mahdi-behnam/linkedaide/commit/aa77483b0cdb4ede47c07998d0d6615d6c843723))
- **relay:** add help, stats, and pending c2 commands to telegram webhook ([6caaba0](https://github.com/mahdi-behnam/linkedaide/commit/6caaba0b3bc7ab2e7d2eee9fd7247c2945bbeaf5))
- **relay:** add ideation trigger endpoint and reaction action handling in worker ([33e0187](https://github.com/mahdi-behnam/linkedaide/commit/33e01874fbabca7588cdb4e177a62340e1dee67b))
- **relay:** add interactive rejection confirmation, feedback tags, and tone menus ([7de5022](https://github.com/mahdi-behnam/linkedaide/commit/7de50223ec82b835300c88b6d17c9603200d0367))
- **relay:** add runner execution notification webhook to broadcast realtime events ([b4644ec](https://github.com/mahdi-behnam/linkedaide/commit/b4644ec626d229554fc70117ec02652104c28dc0))
- **relay:** add scout schedule API and edge cron dispatching ([7ae56b4](https://github.com/mahdi-behnam/linkedaide/commit/7ae56b4539ab6cbbf6f5536d57001f364fa7e79a))
- **relay:** add telegram operator failure feedback on github dispatch errors ([34aa86e](https://github.com/mahdi-behnam/linkedaide/commit/34aa86eff7edc624a97609f199965f192b82d7ac))
- **relay:** allow configuring llm model via environment variable in worker rewrite ([487bc60](https://github.com/mahdi-behnam/linkedaide/commit/487bc609efd00797b517ecec64f14f7df95cad12))
- **relay:** expose active threads in state api endpoint ([a9e68fe](https://github.com/mahdi-behnam/linkedaide/commit/a9e68febc6355d548ea0aec546167dfe850260eb))
- **relay:** handle telegram interactive draft edits and regenerations via webhook ([6a87cd1](https://github.com/mahdi-behnam/linkedaide/commit/6a87cd11ac20951c33f0685293d3935d273912f7))
- **relay:** support reply actions and operator commands in relay worker ([83807fd](https://github.com/mahdi-behnam/linkedaide/commit/83807fdfd840e3f667fa27597d4bc0d842f72168))
- **safety:** implement deterministic anti-cliche guardrail and bounded repair ([914ca55](https://github.com/mahdi-behnam/linkedaide/commit/914ca555d1bc3551cd6fb144b2cf2cffa7e1f573))
- **safety:** send proactive telegram notification when linkedin session expires soon ([1295043](https://github.com/mahdi-behnam/linkedaide/commit/1295043cd78511d8ee6ef800e1f25b7ed18959be))
- **scripts:** add operator helper utilities ([10bdf16](https://github.com/mahdi-behnam/linkedaide/commit/10bdf16aa868552385a4460dae7cb619f9c54bf4))
- **settings:** modernize Session Vault, System Diagnostics, and Settings views ([2c23947](https://github.com/mahdi-behnam/linkedaide/commit/2c23947ff466082673bc4523c6d7500e8e048ada))
- **state:** add durable persistence for connection queue, scheduled posts, and active threads ([ca7ed91](https://github.com/mahdi-behnam/linkedaide/commit/ca7ed91392bf81dc65bd85ca9edc39c8225b07c6))
- **state:** add scout schedule persistence to state stores ([820abb7](https://github.com/mahdi-behnam/linkedaide/commit/820abb73032f22435b32ef64159e5e7d052ab471))
- **state:** add state store and circuit breaker ([08991ff](https://github.com/mahdi-behnam/linkedaide/commit/08991ffa37eecaf308ba8c8538841fc5654a68b8))
- **state:** implement automatic pruning of expired pending actions ([dd9a7f7](https://github.com/mahdi-behnam/linkedaide/commit/dd9a7f7a452fb63b9645c99f6626e6ee5c08b274))
- **state:** implement Cloudflare KV persistence and eliminate git-commit state from CI ([2e0cd75](https://github.com/mahdi-behnam/linkedaide/commit/2e0cd7575c2dd157ee793d66458d94112e7cff4b))
- **state:** implement Cloudflare KV persistence and eliminate git-commit state from CI ([8612447](https://github.com/mahdi-behnam/linkedaide/commit/8612447e36221fc9ca90f7e81f1d9b0d12a2dd02))
- **state:** implement git pull rebase retry loop and conflict handling in state store ([2b55ad6](https://github.com/mahdi-behnam/linkedaide/commit/2b55ad688a404a5bcbec6981841eaf479c138dc6))
- **telegram:** add client and approval keyboards ([9abb599](https://github.com/mahdi-behnam/linkedaide/commit/9abb5992f9b9e5e7f7fc65e41ed4bb961d21afef))
- **telegram:** add inline draft editing, regenerate button, and enhanced suggestion cards ([b499431](https://github.com/mahdi-behnam/linkedaide/commit/b499431a04a7331e214a60bdab65f03606df3509))
- **telegram:** add inline draft editing, regenerate button, and enhanced suggestion cards ([c065021](https://github.com/mahdi-behnam/linkedaide/commit/c06502103565bfe638802db21e80316288047bbb))
- **telegram:** add npm tail script and webhook inspection with smart url detection ([6a9f053](https://github.com/mahdi-behnam/linkedaide/commit/6a9f053a54b809b6bdfba82b7f84fd7227032b08))
- **telegram:** add on-demand mobile post drafting and ad-hoc target scouting ([c21b9c5](https://github.com/mahdi-behnam/linkedaide/commit/c21b9c5014df3e13e6ccda4a15f880c1529ede5d))
- **telegram:** add persistent docked reply keyboard and bot command menu ([5667937](https://github.com/mahdi-behnam/linkedaide/commit/56679379dc34eaa8152eef81241a034dc3978bec))
- **telegram:** add post image preview delivery with automatic HTML fallback ([83c29d8](https://github.com/mahdi-behnam/linkedaide/commit/83c29d846e5a9f15377510f5a167086a332058ed))
- **telegram:** add rejection confirmation, feedback tags, and tone sub-menus ([597ba9a](https://github.com/mahdi-behnam/linkedaide/commit/597ba9abccccf0fa3d6de43150941097f67a33b3))
- **telegram:** display full post excerpts with dynamic length budgeting ([1231800](https://github.com/mahdi-behnam/linkedaide/commit/12318004834f9e5d823f03d600e6fc871d9c50b1))
- **telegram:** ensure persistent docked reply keyboard across all commands and auto-register bot commands on deploy ([f305534](https://github.com/mahdi-behnam/linkedaide/commit/f305534f5fdce31587396f4f57ca53816635d84b))
- **telegram:** implement interactive draft editing via reply and inline callback ([3714858](https://github.com/mahdi-behnam/linkedaide/commit/3714858342a3bfa2405351a33f2d7f64aabe7a11))
- **telegram:** implement operator command and control router for live status and safety controls ([0308b4a](https://github.com/mahdi-behnam/linkedaide/commit/0308b4aa7065b3daf623a6878858b2da9ad1ca2a))
- **telegram:** standardize back/cancel and home menu navigation across bot flows ([a674a42](https://github.com/mahdi-behnam/linkedaide/commit/a674a42824070d25da275828e040d1b791fa4332))
- **telegram:** support dedicated callback action codes and cards for replies and connections ([92f7a15](https://github.com/mahdi-behnam/linkedaide/commit/92f7a1584f4c4b1a81a54127b6fa0f75001fd33e))
- **threads:** implement deep multi-turn thread engagement and reply triage ([0bac2eb](https://github.com/mahdi-behnam/linkedaide/commit/0bac2eb2859a12b6956ad06d5383dd5bea1e3cc7))
- **ui:** add Apple design tokens, system theme detection, and Things 3 navigation chrome ([672f941](https://github.com/mahdi-behnam/linkedaide/commit/672f94101857e4ffc5391dcf387d2967323a89b1))
- **worker:** expand cloudflare relay worker with authenticated control api ([cbe72d4](https://github.com/mahdi-behnam/linkedaide/commit/cbe72d425ffe52ba9c5f71b72b2f9b8df389d4c2))
- **worker:** expand cloudflare relay worker with authenticated control api ([f8471d0](https://github.com/mahdi-behnam/linkedaide/commit/f8471d012b08e4408814f9b1f9b6b5761939986b))

### Bug Fixes

- **browser:** address edge-case hashtag normalization and url scheme handling ([cbdf2d7](https://github.com/mahdi-behnam/linkedaide/commit/cbdf2d7c2491a72e33eecfdd9028939a04f167b7))
- **browser:** refine reaction selector order and submit drift mock matching ([a8ebe05](https://github.com/mahdi-behnam/linkedaide/commit/a8ebe055acf3a32b30a156c7e659fb5fc4c535f2))
- **browser:** require positive DOM verification for connection invitations ([81f8132](https://github.com/mahdi-behnam/linkedaide/commit/81f813233e096e2312e1bea7adf59ebdb4582457))
- **browser:** shield and drain telemetry dom evaluation task upon timeout ([9a2ee11](https://github.com/mahdi-behnam/linkedaide/commit/9a2ee11c1f279008b5d882f9307def703ce8a079))
- **browser:** wait for seamless login redirect and persist refreshed session ([9f88ed7](https://github.com/mahdi-behnam/linkedaide/commit/9f88ed7870d3879aeb2a9114ba90ab1a4aae1d93))
- **ci:** make release checkout resilient to missing tag refs ([7a23f82](https://github.com/mahdi-behnam/linkedaide/commit/7a23f82a6b3ff7690508292dbd627f99d2989b42))
- **core:** resolve ruff formatting, empty env var parsing, and atomic write collisions ([44367d8](https://github.com/mahdi-behnam/linkedaide/commit/44367d81e9c7b9d8e119394da6be990713c44517))
- **desktop:** add author and maintainer email for linux deb packaging ([60f1cc8](https://github.com/mahdi-behnam/linkedaide/commit/60f1cc8b390e3564aa7b58ddf43791d6a52807c3))
- **desktop:** allow testing worker connection with entered form inputs prior to save ([0b41f94](https://github.com/mahdi-behnam/linkedaide/commit/0b41f94866cbb72058f87fcf747c0be8f960a231))
- **desktop:** clarify github PAT scope requirements and improve 403 error reporting ([580a459](https://github.com/mahdi-behnam/linkedaide/commit/580a4593107da67700d79fe2af0d7114456b6e71))
- **desktop:** connect remaining mock actions and persist scheduled posts ([e5a92a3](https://github.com/mahdi-behnam/linkedaide/commit/e5a92a30fb235ad2fbb4df39671195d1f8b85b2d))
- **desktop:** connect triggerScout and togglePause to real backend IPC ([b9740bf](https://github.com/mahdi-behnam/linkedaide/commit/b9740bfe90723741041923b3458d1285a5718f1e))
- **desktop:** extract detailed error messages from worker API and sanitize IPC errors ([fc97c3b](https://github.com/mahdi-behnam/linkedaide/commit/fc97c3bfc4b70dd0e491d3fc1180245de1684514))
- **desktop:** fix cli execution flags and forward connection notes end-to-end ([ef0f155](https://github.com/mahdi-behnam/linkedaide/commit/ef0f15577d7b94eaefe9ff352047b6a7678d8114))
- **desktop:** fix pending actions extraction and add manual queue refresh ([c0cc53d](https://github.com/mahdi-behnam/linkedaide/commit/c0cc53d166e85cd2b77023af096d1654206fae12))
- **desktop:** forward edited draft text and persist local connection notes ([2681b12](https://github.com/mahdi-behnam/linkedaide/commit/2681b12d31ea7ced358b7d574e923016863587e7))
- **desktop:** remove native application menu toolbar ([78961a5](https://github.com/mahdi-behnam/linkedaide/commit/78961a5379a5e290ea7e8ef7902ff25cb1b6837f))
- **desktop:** remove simulated macos traffic light window dots ([3637471](https://github.com/mahdi-behnam/linkedaide/commit/36374713559f4971abbf271848190f1d66bf37ed))
- **desktop:** remove unused import in workerClient ([a3ce321](https://github.com/mahdi-behnam/linkedaide/commit/a3ce321076cdd0f5cad03a17c517ab8fc3e8ff21))
- **desktop:** resolve WebSocket class using ws library in Electron main process ([4a8be83](https://github.com/mahdi-behnam/linkedaide/commit/4a8be83e027f14e5101cdb3cb1999987f34a20e0))
- **desktop:** synchronize outreach queue state with background context updates ([011d73c](https://github.com/mahdi-behnam/linkedaide/commit/011d73cb1ef699547cb9519692815a042edb7c5e))
- **desktop:** throttle state sync and add worker edge caching to respect KV limits ([2661bb9](https://github.com/mahdi-behnam/linkedaide/commit/2661bb9a01586959081c2ed1e0d7b2cd987dc892))
- **execute:** preserve scheduled item lifecycle and record failure state ([668ec50](https://github.com/mahdi-behnam/linkedaide/commit/668ec50a79b232e8dba8b35066922b04ec8ab5b9))
- **graphs:** route thread replies to post_thread_reply and enforce caps ([fb7a276](https://github.com/mahdi-behnam/linkedaide/commit/fb7a276f24fc7457530abd8ce3096bdaa2c23d33))
- **models:** change default used NIM models because of deprecation ([e78d067](https://github.com/mahdi-behnam/linkedaide/commit/e78d0679572b08466cd185b432d6a9f17422cc9b))
- **relay:** align draft rewrite payload format and expand supported tones ([20dc0b7](https://github.com/mahdi-behnam/linkedaide/commit/20dc0b74c927a75b65c8e4266dd89bd669ba944e))
- **relay:** prune secondary message index when consuming pending actions via api ([471d8cb](https://github.com/mahdi-behnam/linkedaide/commit/471d8cb95760c94d4edfa1919daadf198ec5f617))
- **relay:** support connection action codes and handle edit and regenerate callbacks ([ee5489c](https://github.com/mahdi-behnam/linkedaide/commit/ee5489c3432167db150833bba86d9ea067f11e31))
- **safety:** wire state store into circuit breaker checks and executor initialization ([9d71db0](https://github.com/mahdi-behnam/linkedaide/commit/9d71db0df46a214db456e04c7f127c090f7cf9db))
- **scraper:** Enhance and fix DOM selectors for different actions ([444f735](https://github.com/mahdi-behnam/linkedaide/commit/444f735db74868c7f442febf9cecc6e8bf0543b1))
- **security:** guarantee cleanup of temporary unencrypted session files ([ba2d435](https://github.com/mahdi-behnam/linkedaide/commit/ba2d435929e54c828503844b9e765bc82e36ee25))
- **telegram:** track and advance update offset during polling ([8d1acce](https://github.com/mahdi-behnam/linkedaide/commit/8d1accefc2341da5d9a6e283b65ea0ec352f4b04))
- **types:** resolve python static type checking errors across codebase ([ab6f8e1](https://github.com/mahdi-behnam/linkedaide/commit/ab6f8e1c6cf27f6ac49575b505a1725138dde13d))

### Code Refactoring

- **architecture:** decompose monolithic modules into focused handlers and components ([eecdb47](https://github.com/mahdi-behnam/linkedaide/commit/eecdb47258bd96ca454c25ddeb29adab0705d9c8))
- decompose monolithic modules into focused submodules ([f6b445f](https://github.com/mahdi-behnam/linkedaide/commit/f6b445f90c24003485374060fe6b7159d3648937))
- **desktop:** align UI design with Apple Human Interface Guidelines and macOS design system ([c97f41a](https://github.com/mahdi-behnam/linkedaide/commit/c97f41ab819eb7d2a44223e293cff9cdf0949a36))
- **desktop:** eliminate dummy fallback data and implement standard empty states ([a64b315](https://github.com/mahdi-behnam/linkedaide/commit/a64b3151ab7e76ccf5ab63309d04031125c7f676))
- **desktop:** eliminate redundant status labels and copy across UI ([ddc0a39](https://github.com/mahdi-behnam/linkedaide/commit/ddc0a3922b664ab3650efc44f941c6a11634d6f0))
- **desktop:** remove dashboard health check button and sidebar edge sync widget ([f983010](https://github.com/mahdi-behnam/linkedaide/commit/f983010ece85332e43080d49cc253dc4388ace66))
- **desktop:** streamline status indicators and badges to native macOS typography ([e53873f](https://github.com/mahdi-behnam/linkedaide/commit/e53873ff393f4fd42981321393a5636b821e1a0f))
- **desktop:** style unsaved changes dock as rounded rectangle without pulsing dot ([85c0ef1](https://github.com/mahdi-behnam/linkedaide/commit/85c0ef14f81860461fee43a535714eb5d4ffa7bd))
- **desktop:** switch to Apple-style toggles and theme-adaptive picker icons ([53a9f22](https://github.com/mahdi-behnam/linkedaide/commit/53a9f2281f65db69ffab26197da501e3f7742ede))
- **graphs:** remove deprecated procedural thread monitor module in favor of thread graph ([ccb4f2a](https://github.com/mahdi-behnam/linkedaide/commit/ccb4f2a6e9f5272f4d1f25e958e719e69f61ae49))
- **tests:** rename test files for clarity and consistency ([d37ba34](https://github.com/mahdi-behnam/linkedaide/commit/d37ba34d05ef3ebc9968eda120cdd49d05559523))

### Performance Improvements

- **desktop:** code-split view components with dynamic imports and suspense ([b1e071e](https://github.com/mahdi-behnam/linkedaide/commit/b1e071ec0fcbb65fb304dbd377de81c31c9c9ab4))
- **relay:** add secondary message index for constant-time telegram reply lookups ([84cb9ab](https://github.com/mahdi-behnam/linkedaide/commit/84cb9abfa99026e241141345d4f8d6a2b0448b49))

### Documentation

- add comprehensive public documentation suite ([c14386e](https://github.com/mahdi-behnam/linkedaide/commit/c14386e24e9ac67bf64f1ec3ed918533082001c0))
- **agents:** add operating rules and conventions ([7e75f65](https://github.com/mahdi-behnam/linkedaide/commit/7e75f65ae93f441fa8ef0dd5cf1e92daaf821197))
- **agents:** require commit body description for non-trivial changes ([c81869d](https://github.com/mahdi-behnam/linkedaide/commit/c81869d866657996f53241833136a19e4ac2d19f))
- **config:** synchronize .env.example and document advanced subsystems in README ([e0a555f](https://github.com/mahdi-behnam/linkedaide/commit/e0a555fe674a41ba3f7b87ffe6214d56559c1afc))
- **desktop:** document Desktop App launch instructions and day-to-day operational workflow ([764fb1b](https://github.com/mahdi-behnam/linkedaide/commit/764fb1b8e12da4addc5052dcaf351a1472904b99))
- **desktop:** guide users to standalone downloads and document source builds ([ed6aa71](https://github.com/mahdi-behnam/linkedaide/commit/ed6aa71c8a2eec90877b68cf1ddbed516adf6e27))
- **license:** add MIT license ([bc4be4b](https://github.com/mahdi-behnam/linkedaide/commit/bc4be4baa7474af529f67024971c7fe381f57c5c))
- **readme:** clarify capabilities, fix onboarding setup, and add CLI poll and ideate commands ([84618fa](https://github.com/mahdi-behnam/linkedaide/commit/84618fa040f122be06e22d568260fde21e5c3625))
- **relay:** document NVIDIA_NIM_API_KEY secret for worker draft rewrites ([bbcf23a](https://github.com/mahdi-behnam/linkedaide/commit/bbcf23ac98783aee93077ebf471d52375d7ed1c6))
- **setup:** document Cloudflare KV and R2 provisioning steps before worker deployment ([632fa08](https://github.com/mahdi-behnam/linkedaide/commit/632fa0891be2639e2c7d260d5ceae7a8648b83e2))
- **setup:** document Cloudflare KV secrets required for GitHub Actions ([f0c58a2](https://github.com/mahdi-behnam/linkedaide/commit/f0c58a2a6f607d6bdea57a1599deace8a26d3cc5))
- **setup:** enhance setup guide with KV ID instructions and R2 dashboard activation details ([64f9394](https://github.com/mahdi-behnam/linkedaide/commit/64f93941edd40a1a8f684a0db50bcc0aa85f83b4))
- **setup:** make Cloudflare R2 optional by default and document zero-card setup ([8d41787](https://github.com/mahdi-behnam/linkedaide/commit/8d417876d2edce94f899489f612457f1feffe76b))
- update configuration references, directory tree, and cli documentation ([c35ceab](https://github.com/mahdi-behnam/linkedaide/commit/c35ceab0f483b778ac87c8c132a36eefe47a5733))
- update system architecture and configuration guide with recent features ([83b96a2](https://github.com/mahdi-behnam/linkedaide/commit/83b96a2c9cb32e1644c911f8b976a07064398057))

### Tests

- **adversarial:** add adversarial challenge test suites for reliability hardening ([407cfe9](https://github.com/mahdi-behnam/linkedaide/commit/407cfe951ec6cc94b49780f86b70f5b9ef6d4cd6))
- **browser:** add unit and integration tests for targeted scouting ([5fbbedd](https://github.com/mahdi-behnam/linkedaide/commit/5fbbedd53651f4ec0c9fe1781f0b52ee03cb6507))
- **coverage:** expand test suites across orchestration flows and error paths to exceed 90% coverage ([982ef3a](https://github.com/mahdi-behnam/linkedaide/commit/982ef3a15a8e1e6b66101e97f2a8e8ac3f9d1d65))
- **desktop:** wrap analytics refresh event in act to eliminate test warning ([e350cbb](https://github.com/mahdi-behnam/linkedaide/commit/e350cbb250b9c6f9d0fd00c5615e2fd5dbe8f66b))
- **graphs:** add topology invariant unit tests ([f1b21b0](https://github.com/mahdi-behnam/linkedaide/commit/f1b21b0d170e9edd27ae3740884bdc208dafef5c))
- **graphs:** add unit tests for ideation graph and orchestration ([fb32812](https://github.com/mahdi-behnam/linkedaide/commit/fb32812775089678320967e54778b9ccbe27ef50))
- **orchestration:** fix date rollover in command handler status test ([f0d8df8](https://github.com/mahdi-behnam/linkedaide/commit/f0d8df85751ea55d680e1f0c949929ebaf89dc1c))
- **relay:** fix execution context typing in r2 tests and add typecheck script ([81123ec](https://github.com/mahdi-behnam/linkedaide/commit/81123ecbfbef6e547b8ec8a1d6203a2a816e2096))
- **state:** mark git pre-receive test hooks executable ([0bad2dd](https://github.com/mahdi-behnam/linkedaide/commit/0bad2dd4252630fe63c7009830d42b5520a6c5ce))
- **state:** mark git pre-receive test hooks executable ([b65f4a3](https://github.com/mahdi-behnam/linkedaide/commit/b65f4a3fb73d26c5cc977192b5c575cbbbfef5c3))
- **telegram:** add comprehensive unit and integration tests for draft editing and command router ([ce8f4d9](https://github.com/mahdi-behnam/linkedaide/commit/ce8f4d9bf27de84c8b1857a78ec73f9bbecf3b17))
- **workflow:** add comprehensive test suites for expired pruning, organic reactions, and engagement styles ([a06c6da](https://github.com/mahdi-behnam/linkedaide/commit/a06c6da6fa54426ee0e6534f242da0e5255e1707))

### Continuous Integration

- **actions:** add CI and automation workflows ([9e97795](https://github.com/mahdi-behnam/linkedaide/commit/9e9779503d676dab9368fe6daf760ccd9b85048e))
- **actions:** add max connections per day limit to workflows ([a91c4dd](https://github.com/mahdi-behnam/linkedaide/commit/a91c4dd49613c224017580b496a9a68e4b7be4d2))
- **actions:** add scheduled thread reply monitoring workflow ([b04b845](https://github.com/mahdi-behnam/linkedaide/commit/b04b845a9a792d67378317438add9e2061f2763b))
- **actions:** align artifact retention, ideation persona, and desktop release flags ([0a14540](https://github.com/mahdi-behnam/linkedaide/commit/0a14540e45fd0e21182eaf3684385f77ca05fd21))
- **actions:** enforce bash shell for desktop releases and add electron build to ci ([c834084](https://github.com/mahdi-behnam/linkedaide/commit/c8340842740d23c6d956f22427c88b56cc621ade))
- **actions:** expose target urls and hashtags in scout workflow ([950e6a2](https://github.com/mahdi-behnam/linkedaide/commit/950e6a26875fd027d761db0ce2dec473b998840f))
- **actions:** inject worker url and api secret for r2 audit screenshots ([73bbe43](https://github.com/mahdi-behnam/linkedaide/commit/73bbe4398231a0f29cba2198f02e3b51d57b2b21))
- **actions:** pass session encryption key to execution steps for cookie keepalive ([5421d33](https://github.com/mahdi-behnam/linkedaide/commit/5421d330f938737cb86043e3519f072c2855c882))
- **workflows:** add type check and test jobs for worker and desktop app ([d5cdb03](https://github.com/mahdi-behnam/linkedaide/commit/d5cdb03c1c7d2f7dd7e2789e5dcdccae61f4ae18))

## [1.1.0](https://github.com/mahdi-behnam/linkedaide/compare/LinkedAide-v1.0.0...LinkedAide-v1.1.0) (2026-10-15)

### Features

- **browser:** add organic pre-comment reaction simulation and humanized dwell timing ([faa9068](https://github.com/mahdi-behnam/linkedaide/commit/faa90685422770d696f6777fba26e6945a44d9c4))
- **browser:** add Playwright session and actions ([1d9c3ec](https://github.com/mahdi-behnam/linkedaide/commit/1d9c3ec811555b329de6b22c39b9420909788cac))
- **browser:** add targeted scouting for hashtags and custom feeds ([b9f8228](https://github.com/mahdi-behnam/linkedaide/commit/b9f822836c94e4b1f4a7f78854b8e1317ac00b7b))
- **browser:** extract author profile url directly from feed cards ([baae33c](https://github.com/mahdi-behnam/linkedaide/commit/baae33c1e9d0ba1b58d404bc99f444ed17689410))
- **browser:** implement 4-tier self-healing selectors and residential proxy gateway ([19c3df7](https://github.com/mahdi-behnam/linkedaide/commit/19c3df7f979da670f1b0968370b6c593606350ff))
- **browser:** implement active post-submission DOM verification and error capture ([e8a0271](https://github.com/mahdi-behnam/linkedaide/commit/e8a02711a3e351537aa714143ca087370b5c376e))
- **browser:** implement behavioral biometrics and rolling cookie keepalive ([a43d9a5](https://github.com/mahdi-behnam/linkedaide/commit/a43d9a5a910e51f2fef6b8ade50f98015babd8e6))
- **browser:** implement sanitized DOM telemetry and selector drift diagnostics ([3d87d7d](https://github.com/mahdi-behnam/linkedaide/commit/3d87d7dacd2444707825346a0de92d245ade49e7))
- **browser:** modernize DOM selectors, auto-decrypt sessions, and add file logging ([e7c48d8](https://github.com/mahdi-behnam/linkedaide/commit/e7c48d8b6fa1cce270d13cc5687ba8606bdf66c6))
- **browser:** support downloading remote r2 media assets for scheduled post submissions ([bcae442](https://github.com/mahdi-behnam/linkedaide/commit/bcae442702c2d97d3696e12f61949359e3ebd11c))
- **browser:** wire self-healing selector engine into action executor mixins ([a4b6f1e](https://github.com/mahdi-behnam/linkedaide/commit/a4b6f1e28e04fd606625b2a838b60643b9b81336))
- **ci:** automate desktop release pipeline and add download badges to README ([0d94be7](https://github.com/mahdi-behnam/linkedaide/commit/0d94be7326239f43a1c403cf8956523d051bb317))
- **cli:** add dedicated connection outreach command ([e481b00](https://github.com/mahdi-behnam/linkedaide/commit/e481b0034b367556ea6133c8304120e2ed7fe955))
- **cli:** add DESKTOP_API_SECRET automated generation to scripts, setup wizard, and docs ([ce90f86](https://github.com/mahdi-behnam/linkedaide/commit/ce90f86188fcb2beea605681ec3507253d1dc1c6))
- **cli:** add package main entrypoint and register all subcommands ([226d666](https://github.com/mahdi-behnam/linkedaide/commit/226d66649d1d6cd2356549a92582039a9748e6c3))
- **cli:** add targeted connection outreach scout command ([d1ca693](https://github.com/mahdi-behnam/linkedaide/commit/d1ca693988af9eaa27f6191bc1878e85db725699))
- **cli:** add unified cli with interactive setup wizard and doctor diagnostics ([739d462](https://github.com/mahdi-behnam/linkedaide/commit/739d462fc96d095332d11076a50009ba3ee637f2))
- **composer:** implement 2-pane Post Composer Studio and Content Calendar ([a3cc3ea](https://github.com/mahdi-behnam/linkedaide/commit/a3cc3eada82a476f3262fbfa97fb9d0c8806ef34))
- **dashboard:** align Command Center and Growth Analytics with Serene Craft design ([5695355](https://github.com/mahdi-behnam/linkedaide/commit/569535512b61862e0b16325b701f846560f02211))
- **desktop:** add ⌘k command palette and tab navigation history ([3253088](https://github.com/mahdi-behnam/linkedaide/commit/32530888cc04d8a4c75ba8cb41e895aafb817f34))
- **desktop:** add application-wide timezone configuration and formatting ([0f6b6b1](https://github.com/mahdi-behnam/linkedaide/commit/0f6b6b1fde307ef339261f0e07409421fa434d81))
- **desktop:** add daily connection outreach limit to safety settings and align counters ([ae7fa45](https://github.com/mahdi-behnam/linkedaide/commit/ae7fa455d4e6671ab66645a1aaebfb9d6813bc6b))
- **desktop:** add durable r2 media upload bridge for post composer studio ([5d847d6](https://github.com/mahdi-behnam/linkedaide/commit/5d847d66996a6e236458dd818bf9ea16224870d4))
- **desktop:** add dynamic NVIDIA NIM model selector with live catalog fetching ([9cdc06b](https://github.com/mahdi-behnam/linkedaide/commit/9cdc06bfc9904367d215d71cc4796c31b7902db2))
- **desktop:** add floating unsaved changes dock and navigation lock modal in settings ([55e2301](https://github.com/mahdi-behnam/linkedaide/commit/55e23018ffe1b750fd11db4d3bec3e4130accf83))
- **desktop:** add scout targeting and engine parameters to settings ([a3e3e5d](https://github.com/mahdi-behnam/linkedaide/commit/a3e3e5da9c55dae516d1d904e29e7a109e33394f))
- **desktop:** add self-healing electron prestart script and automated multi-platform release workflow ([e8e8ef2](https://github.com/mahdi-behnam/linkedaide/commit/e8e8ef2f64f3b7df24e5d1a47c8da624a3e27fa4))
- **desktop:** build linear-style component system and navigation layout ([382bd36](https://github.com/mahdi-behnam/linkedaide/commit/382bd3666229d1875331ab170dbc117c38eba010))
- **desktop:** build linear-style component system and navigation layout ([e89c972](https://github.com/mahdi-behnam/linkedaide/commit/e89c972a1f68688931bbb2b58d5993aeb4a4f783))
- **desktop:** configure github cloud runner credentials and audit diagnostics ([05d1780](https://github.com/mahdi-behnam/linkedaide/commit/05d1780f738cf52bde30c71030cfbfdfc0268d9d))
- **desktop:** declare session vault IPC contracts ([45e3572](https://github.com/mahdi-behnam/linkedaide/commit/45e3572975610a0e3c47f82da2869c61b367058c))
- **desktop:** dynamically bind auto-polling interval in approval queue status bar ([25a9fef](https://github.com/mahdi-behnam/linkedaide/commit/25a9fefa1c548b890f730680f33126e0dfd5937b))
- **desktop:** enable executing agent doctor diagnostic suite from desktop ([82a114c](https://github.com/mahdi-behnam/linkedaide/commit/82a114c7b0ce0406267cf5e1b8a69240ad764cef))
- **desktop:** expand audit history action types and filtering ([80596ca](https://github.com/mahdi-behnam/linkedaide/commit/80596ca8c7a8f5bb54c8463b1ec6b9c1f73e6bce))
- **desktop:** implement approval queue with ai tone rewriting studio ([51ca2e5](https://github.com/mahdi-behnam/linkedaide/commit/51ca2e5bb5164c2cd9cab6239fab1ec87d03f5fa))
- **desktop:** implement configurable scout schedule management in UI and bridge ([bfd6e5e](https://github.com/mahdi-behnam/linkedaide/commit/bfd6e5e79e03404d0b7d32e927123d3cf7af8fd1))
- **desktop:** implement electron main process secure ipc and fernet crypto ([aab4db7](https://github.com/mahdi-behnam/linkedaide/commit/aab4db7b3a59b3cf458080e9fb6f4de1477acfeb))
- **desktop:** implement electron main process secure ipc and fernet crypto ([246028f](https://github.com/mahdi-behnam/linkedaide/commit/246028fe253281b17f5e520669ac521fa9be9449))
- **desktop:** implement hidden title bar with window controls overlay ([9c04ff5](https://github.com/mahdi-behnam/linkedaide/commit/9c04ff5d4a25e3d8cbea870a7fa05fb876665d92))
- **desktop:** implement interactive dual-mode settings and local runner execution ([205f40e](https://github.com/mahdi-behnam/linkedaide/commit/205f40ec56f8a2dd16365fff6371504a74c0d92a))
- **desktop:** implement linkedin session vault and embedded auth ([ca7d9fb](https://github.com/mahdi-behnam/linkedaide/commit/ca7d9fbc7ffe008eaebdc6718bb4c3c2516a68a0))
- **desktop:** implement post composer studio and visual calendar planner ([1cb9294](https://github.com/mahdi-behnam/linkedaide/commit/1cb9294c388236651ead94f19d7bd8ede3e80c21))
- **desktop:** implement power user keyboard shortcuts and cheat sheet overlay ([4f02f5c](https://github.com/mahdi-behnam/linkedaide/commit/4f02f5c926c4e6a14cbc4cbdb253943076422f1a))
- **desktop:** implement system tray and background notification engine ([05ece9a](https://github.com/mahdi-behnam/linkedaide/commit/05ece9a550f748760ea2f4178e616591443c2aec))
- **desktop:** implement voice audio dictation and linkedin growth analytics dashboard ([8be0e28](https://github.com/mahdi-behnam/linkedaide/commit/8be0e2877455714b7420988ecc16b9781caa104d))
- **desktop:** integrate LinkedAide branding, dynamic status icons, and tray assets ([d6944c2](https://github.com/mahdi-behnam/linkedaide/commit/d6944c228f935a9b8c7ae2a223615f055a24a0a4))
- **desktop:** integrate post scheduling, outreach queue, and worker relay endpoints ([4486539](https://github.com/mahdi-behnam/linkedaide/commit/4486539b4b85fb008c630b2ffe0e66fb46abcc53))
- **desktop:** populate and synchronize default automated scout comment windows ([915db03](https://github.com/mahdi-behnam/linkedaide/commit/915db0306e521530edc766374d19874160c4c9da))
- **desktop:** propagate headed mode flag to local scout process execution ([634bd8e](https://github.com/mahdi-behnam/linkedaide/commit/634bd8e20fe6fd669882e56b383ac917fcdd7d21))
- **desktop:** refine UI ergonomics, OS shortcuts, and notification system ([2ac6ece](https://github.com/mahdi-behnam/linkedaide/commit/2ac6ece5ad083130afaaabc1a4bdb57e8eb97e49))
- **desktop:** restore native application menu and wire ipc action dispatch ([3424f2f](https://github.com/mahdi-behnam/linkedaide/commit/3424f2f440934097e5c6489c90192a63caa566a2))
- **desktop:** wire post ideation trigger, varied reactions, and thread replies in approval queue ([5124882](https://github.com/mahdi-behnam/linkedaide/commit/51248822365452fcc5302f5daa50f8951a6113fe))
- **docs:** add secret generator script and improve setup guide ([d1f44d1](https://github.com/mahdi-behnam/linkedaide/commit/d1f44d18a42668d3fb6f6a225c9e9c0d76753f21))
- **execute:** add progressive lifecycle updates and direct LinkedIn verification links ([cb8bd93](https://github.com/mahdi-behnam/linkedaide/commit/cb8bd93abb2fce22359ce3fc32b4d23c211910f9))
- **execute:** manage scheduled post lifecycle and support media attachments ([bb652c8](https://github.com/mahdi-behnam/linkedaide/commit/bb652c8f915c47d8b6659362ab7e81d667be5737))
- **graphs:** add LangGraph workflow machines ([283dffc](https://github.com/mahdi-behnam/linkedaide/commit/283dffcd3353ab6b5a98f627651f912a3577632f))
- **graphs:** implement original post ideation graph and workflow ([4b6acb0](https://github.com/mahdi-behnam/linkedaide/commit/4b6acb0d845fc0577eefa556aca3f5be8d2cc235))
- **graphs:** implement thread monitor graph and state machine ([00d2d13](https://github.com/mahdi-behnam/linkedaide/commit/00d2d133670d4b54d14f7095ec8eb39f6ac170c6))
- **graphs:** wire connection outreach, thread monitoring, and execution dispatch ([7455ee0](https://github.com/mahdi-behnam/linkedaide/commit/7455ee0ebeaf4be02622a53861f260753f26f64a))
- **graphs:** wire reaction routing and execution across scout and execute graphs ([96e81f5](https://github.com/mahdi-behnam/linkedaide/commit/96e81f51048cd49e9790b2f33e9f7bd535ebced5))
- **llm:** add multi-provider support for openai, anthropic, gemini, groq, and ollama ([e088647](https://github.com/mahdi-behnam/linkedaide/commit/e0886470e57dcfb6f063713499f73aeff8ce02d8))
- **llm:** add multi-provider support for openai, anthropic, gemini, groq, and ollama ([1f41b6b](https://github.com/mahdi-behnam/linkedaide/commit/1f41b6b3dbb670b657cd7eac8bf3021393fb9987))
- **llm:** add NVIDIA NIM LangChain integration ([12fbe60](https://github.com/mahdi-behnam/linkedaide/commit/12fbe601c5b22cf528380cb9edad8e23f0036511))
- **llm:** enforce anti-cliche guardrails on thread replies and post ideation ([6ad615c](https://github.com/mahdi-behnam/linkedaide/commit/6ad615c1bcc8719df75891ba241e224110196696))
- **llm:** implement multimodal vision analysis and diagram-grounded drafting ([348a751](https://github.com/mahdi-behnam/linkedaide/commit/348a75148a8de82fa6f4a6571c8a74bb00a0c8b5))
- **llm:** implement persona voice vector memory and dynamic few-shot injection ([506ea26](https://github.com/mahdi-behnam/linkedaide/commit/506ea26832979742eaed169c8f305d71003bb4bf))
- **llm:** introduce dynamic engagement styles and contextual prompt adaptation ([16505d8](https://github.com/mahdi-behnam/linkedaide/commit/16505d8993a371be3a78c56605978265763a0058))
- **llm:** support nvidia nim vision models in multimodal extractor ([9b80793](https://github.com/mahdi-behnam/linkedaide/commit/9b80793dd78a28c9fcb94dbb165a248377461421))
- **llm:** wire voice memory continuous learning with durable state persistence ([99deb88](https://github.com/mahdi-behnam/linkedaide/commit/99deb88e0372dcd59cbf2ffd7e84fded55ba772a))
- **models:** add domain schemas and config ([ce420f3](https://github.com/mahdi-behnam/linkedaide/commit/ce420f3c4d488ecac35277e81784b73190046a9d))
- **models:** add reaction types, triage recommendations, and pending action support ([6279d56](https://github.com/mahdi-behnam/linkedaide/commit/6279d56e9beba5bdab02fcd0d76fd8fb80ae9b1d))
- **orchestration:** add process entrypoint flows ([e1e3ae7](https://github.com/mahdi-behnam/linkedaide/commit/e1e3ae7e76382398e24eb5a9b6744b8e8df0088d))
- **orchestration:** implement thread reply monitoring orchestration and cli command ([a5944c1](https://github.com/mahdi-behnam/linkedaide/commit/a5944c176de1c17d37b8572066423e9b00310177))
- **outreach:** implement connection request hitl queue and safety caps ([7d4b640](https://github.com/mahdi-behnam/linkedaide/commit/7d4b64034a36b3db2134d3367065ee245081ba0a))
- **queue:** modernize Approval Queue and Outreach Queue with Things 3 layout ([2749ef1](https://github.com/mahdi-behnam/linkedaide/commit/2749ef1fee78a0c663be0706c79bcd5ff7729d99))
- **r2:** implement cloudflare r2 media vault for audit screenshots and carousel assets ([579ca40](https://github.com/mahdi-behnam/linkedaide/commit/579ca400bdd8a327af4883aba4e4ce3803563082))
- **realtime:** implement cloudflare worker websocket push hub and instant desktop sync ([82616c4](https://github.com/mahdi-behnam/linkedaide/commit/82616c4fba557f048245db015d9e54c8f5c248dd))
- **relay:** add Cloudflare Worker Telegram relay ([ed7dcdc](https://github.com/mahdi-behnam/linkedaide/commit/ed7dcdc939462f53190af907e1113bbc41127128))
- **relay:** add cron trigger and handler for scheduled post dispatch ([aa77483](https://github.com/mahdi-behnam/linkedaide/commit/aa77483b0cdb4ede47c07998d0d6615d6c843723))
- **relay:** add help, stats, and pending c2 commands to telegram webhook ([6caaba0](https://github.com/mahdi-behnam/linkedaide/commit/6caaba0b3bc7ab2e7d2eee9fd7247c2945bbeaf5))
- **relay:** add ideation trigger endpoint and reaction action handling in worker ([33e0187](https://github.com/mahdi-behnam/linkedaide/commit/33e01874fbabca7588cdb4e177a62340e1dee67b))
- **relay:** add interactive rejection confirmation, feedback tags, and tone menus ([7de5022](https://github.com/mahdi-behnam/linkedaide/commit/7de50223ec82b835300c88b6d17c9603200d0367))
- **relay:** add runner execution notification webhook to broadcast realtime events ([b4644ec](https://github.com/mahdi-behnam/linkedaide/commit/b4644ec626d229554fc70117ec02652104c28dc0))
- **relay:** add scout schedule API and edge cron dispatching ([7ae56b4](https://github.com/mahdi-behnam/linkedaide/commit/7ae56b4539ab6cbbf6f5536d57001f364fa7e79a))
- **relay:** add telegram operator failure feedback on github dispatch errors ([34aa86e](https://github.com/mahdi-behnam/linkedaide/commit/34aa86eff7edc624a97609f199965f192b82d7ac))
- **relay:** allow configuring llm model via environment variable in worker rewrite ([487bc60](https://github.com/mahdi-behnam/linkedaide/commit/487bc609efd00797b517ecec64f14f7df95cad12))
- **relay:** expose active threads in state api endpoint ([a9e68fe](https://github.com/mahdi-behnam/linkedaide/commit/a9e68febc6355d548ea0aec546167dfe850260eb))
- **relay:** handle telegram interactive draft edits and regenerations via webhook ([6a87cd1](https://github.com/mahdi-behnam/linkedaide/commit/6a87cd11ac20951c33f0685293d3935d273912f7))
- **relay:** support reply actions and operator commands in relay worker ([83807fd](https://github.com/mahdi-behnam/linkedaide/commit/83807fdfd840e3f667fa27597d4bc0d842f72168))
- **safety:** implement deterministic anti-cliche guardrail and bounded repair ([914ca55](https://github.com/mahdi-behnam/linkedaide/commit/914ca555d1bc3551cd6fb144b2cf2cffa7e1f573))
- **safety:** send proactive telegram notification when linkedin session expires soon ([1295043](https://github.com/mahdi-behnam/linkedaide/commit/1295043cd78511d8ee6ef800e1f25b7ed18959be))
- **scripts:** add operator helper utilities ([10bdf16](https://github.com/mahdi-behnam/linkedaide/commit/10bdf16aa868552385a4460dae7cb619f9c54bf4))
- **settings:** modernize Session Vault, System Diagnostics, and Settings views ([2c23947](https://github.com/mahdi-behnam/linkedaide/commit/2c23947ff466082673bc4523c6d7500e8e048ada))
- **state:** add durable persistence for connection queue, scheduled posts, and active threads ([ca7ed91](https://github.com/mahdi-behnam/linkedaide/commit/ca7ed91392bf81dc65bd85ca9edc39c8225b07c6))
- **state:** add scout schedule persistence to state stores ([820abb7](https://github.com/mahdi-behnam/linkedaide/commit/820abb73032f22435b32ef64159e5e7d052ab471))
- **state:** add state store and circuit breaker ([08991ff](https://github.com/mahdi-behnam/linkedaide/commit/08991ffa37eecaf308ba8c8538841fc5654a68b8))
- **state:** implement automatic pruning of expired pending actions ([dd9a7f7](https://github.com/mahdi-behnam/linkedaide/commit/dd9a7f7a452fb63b9645c99f6626e6ee5c08b274))
- **state:** implement Cloudflare KV persistence and eliminate git-commit state from CI ([2e0cd75](https://github.com/mahdi-behnam/linkedaide/commit/2e0cd7575c2dd157ee793d66458d94112e7cff4b))
- **state:** implement Cloudflare KV persistence and eliminate git-commit state from CI ([8612447](https://github.com/mahdi-behnam/linkedaide/commit/8612447e36221fc9ca90f7e81f1d9b0d12a2dd02))
- **state:** implement git pull rebase retry loop and conflict handling in state store ([2b55ad6](https://github.com/mahdi-behnam/linkedaide/commit/2b55ad688a404a5bcbec6981841eaf479c138dc6))
- **telegram:** add client and approval keyboards ([9abb599](https://github.com/mahdi-behnam/linkedaide/commit/9abb5992f9b9e5e7f7fc65e41ed4bb961d21afef))
- **telegram:** add inline draft editing, regenerate button, and enhanced suggestion cards ([b499431](https://github.com/mahdi-behnam/linkedaide/commit/b499431a04a7331e214a60bdab65f03606df3509))
- **telegram:** add inline draft editing, regenerate button, and enhanced suggestion cards ([c065021](https://github.com/mahdi-behnam/linkedaide/commit/c06502103565bfe638802db21e80316288047bbb))
- **telegram:** add npm tail script and webhook inspection with smart url detection ([6a9f053](https://github.com/mahdi-behnam/linkedaide/commit/6a9f053a54b809b6bdfba82b7f84fd7227032b08))
- **telegram:** add on-demand mobile post drafting and ad-hoc target scouting ([c21b9c5](https://github.com/mahdi-behnam/linkedaide/commit/c21b9c5014df3e13e6ccda4a15f880c1529ede5d))
- **telegram:** add persistent docked reply keyboard and bot command menu ([5667937](https://github.com/mahdi-behnam/linkedaide/commit/56679379dc34eaa8152eef81241a034dc3978bec))
- **telegram:** add post image preview delivery with automatic HTML fallback ([83c29d8](https://github.com/mahdi-behnam/linkedaide/commit/83c29d846e5a9f15377510f5a167086a332058ed))
- **telegram:** add rejection confirmation, feedback tags, and tone sub-menus ([597ba9a](https://github.com/mahdi-behnam/linkedaide/commit/597ba9abccccf0fa3d6de43150941097f67a33b3))
- **telegram:** display full post excerpts with dynamic length budgeting ([1231800](https://github.com/mahdi-behnam/linkedaide/commit/12318004834f9e5d823f03d600e6fc871d9c50b1))
- **telegram:** ensure persistent docked reply keyboard across all commands and auto-register bot commands on deploy ([f305534](https://github.com/mahdi-behnam/linkedaide/commit/f305534f5fdce31587396f4f57ca53816635d84b))
- **telegram:** implement interactive draft editing via reply and inline callback ([3714858](https://github.com/mahdi-behnam/linkedaide/commit/3714858342a3bfa2405351a33f2d7f64aabe7a11))
- **telegram:** implement operator command and control router for live status and safety controls ([0308b4a](https://github.com/mahdi-behnam/linkedaide/commit/0308b4aa7065b3daf623a6878858b2da9ad1ca2a))
- **telegram:** standardize back/cancel and home menu navigation across bot flows ([a674a42](https://github.com/mahdi-behnam/linkedaide/commit/a674a42824070d25da275828e040d1b791fa4332))
- **telegram:** support dedicated callback action codes and cards for replies and connections ([92f7a15](https://github.com/mahdi-behnam/linkedaide/commit/92f7a1584f4c4b1a81a54127b6fa0f75001fd33e))
- **threads:** implement deep multi-turn thread engagement and reply triage ([0bac2eb](https://github.com/mahdi-behnam/linkedaide/commit/0bac2eb2859a12b6956ad06d5383dd5bea1e3cc7))
- **ui:** add Apple design tokens, system theme detection, and Things 3 navigation chrome ([672f941](https://github.com/mahdi-behnam/linkedaide/commit/672f94101857e4ffc5391dcf387d2967323a89b1))
- **worker:** expand cloudflare relay worker with authenticated control api ([cbe72d4](https://github.com/mahdi-behnam/linkedaide/commit/cbe72d425ffe52ba9c5f71b72b2f9b8df389d4c2))
- **worker:** expand cloudflare relay worker with authenticated control api ([f8471d0](https://github.com/mahdi-behnam/linkedaide/commit/f8471d012b08e4408814f9b1f9b6b5761939986b))

### Bug Fixes

- **browser:** address edge-case hashtag normalization and url scheme handling ([cbdf2d7](https://github.com/mahdi-behnam/linkedaide/commit/cbdf2d7c2491a72e33eecfdd9028939a04f167b7))
- **browser:** refine reaction selector order and submit drift mock matching ([a8ebe05](https://github.com/mahdi-behnam/linkedaide/commit/a8ebe055acf3a32b30a156c7e659fb5fc4c535f2))
- **browser:** require positive DOM verification for connection invitations ([81f8132](https://github.com/mahdi-behnam/linkedaide/commit/81f813233e096e2312e1bea7adf59ebdb4582457))
- **browser:** shield and drain telemetry dom evaluation task upon timeout ([9a2ee11](https://github.com/mahdi-behnam/linkedaide/commit/9a2ee11c1f279008b5d882f9307def703ce8a079))
- **browser:** wait for seamless login redirect and persist refreshed session ([9f88ed7](https://github.com/mahdi-behnam/linkedaide/commit/9f88ed7870d3879aeb2a9114ba90ab1a4aae1d93))
- **ci:** make release checkout resilient to missing tag refs ([7a23f82](https://github.com/mahdi-behnam/linkedaide/commit/7a23f82a6b3ff7690508292dbd627f99d2989b42))
- **core:** resolve ruff formatting, empty env var parsing, and atomic write collisions ([44367d8](https://github.com/mahdi-behnam/linkedaide/commit/44367d81e9c7b9d8e119394da6be990713c44517))
- **desktop:** allow testing worker connection with entered form inputs prior to save ([0b41f94](https://github.com/mahdi-behnam/linkedaide/commit/0b41f94866cbb72058f87fcf747c0be8f960a231))
- **desktop:** clarify github PAT scope requirements and improve 403 error reporting ([580a459](https://github.com/mahdi-behnam/linkedaide/commit/580a4593107da67700d79fe2af0d7114456b6e71))
- **desktop:** connect remaining mock actions and persist scheduled posts ([e5a92a3](https://github.com/mahdi-behnam/linkedaide/commit/e5a92a30fb235ad2fbb4df39671195d1f8b85b2d))
- **desktop:** connect triggerScout and togglePause to real backend IPC ([b9740bf](https://github.com/mahdi-behnam/linkedaide/commit/b9740bfe90723741041923b3458d1285a5718f1e))
- **desktop:** extract detailed error messages from worker API and sanitize IPC errors ([fc97c3b](https://github.com/mahdi-behnam/linkedaide/commit/fc97c3bfc4b70dd0e491d3fc1180245de1684514))
- **desktop:** fix cli execution flags and forward connection notes end-to-end ([ef0f155](https://github.com/mahdi-behnam/linkedaide/commit/ef0f15577d7b94eaefe9ff352047b6a7678d8114))
- **desktop:** fix pending actions extraction and add manual queue refresh ([c0cc53d](https://github.com/mahdi-behnam/linkedaide/commit/c0cc53d166e85cd2b77023af096d1654206fae12))
- **desktop:** forward edited draft text and persist local connection notes ([2681b12](https://github.com/mahdi-behnam/linkedaide/commit/2681b12d31ea7ced358b7d574e923016863587e7))
- **desktop:** remove native application menu toolbar ([78961a5](https://github.com/mahdi-behnam/linkedaide/commit/78961a5379a5e290ea7e8ef7902ff25cb1b6837f))
- **desktop:** remove simulated macos traffic light window dots ([3637471](https://github.com/mahdi-behnam/linkedaide/commit/36374713559f4971abbf271848190f1d66bf37ed))
- **desktop:** remove unused import in workerClient ([a3ce321](https://github.com/mahdi-behnam/linkedaide/commit/a3ce321076cdd0f5cad03a17c517ab8fc3e8ff21))
- **desktop:** resolve WebSocket class using ws library in Electron main process ([4a8be83](https://github.com/mahdi-behnam/linkedaide/commit/4a8be83e027f14e5101cdb3cb1999987f34a20e0))
- **desktop:** synchronize outreach queue state with background context updates ([011d73c](https://github.com/mahdi-behnam/linkedaide/commit/011d73cb1ef699547cb9519692815a042edb7c5e))
- **desktop:** throttle state sync and add worker edge caching to respect KV limits ([2661bb9](https://github.com/mahdi-behnam/linkedaide/commit/2661bb9a01586959081c2ed1e0d7b2cd987dc892))
- **execute:** preserve scheduled item lifecycle and record failure state ([668ec50](https://github.com/mahdi-behnam/linkedaide/commit/668ec50a79b232e8dba8b35066922b04ec8ab5b9))
- **graphs:** route thread replies to post_thread_reply and enforce caps ([fb7a276](https://github.com/mahdi-behnam/linkedaide/commit/fb7a276f24fc7457530abd8ce3096bdaa2c23d33))
- **models:** change default used NIM models because of deprecation ([e78d067](https://github.com/mahdi-behnam/linkedaide/commit/e78d0679572b08466cd185b432d6a9f17422cc9b))
- **relay:** align draft rewrite payload format and expand supported tones ([20dc0b7](https://github.com/mahdi-behnam/linkedaide/commit/20dc0b74c927a75b65c8e4266dd89bd669ba944e))
- **relay:** prune secondary message index when consuming pending actions via api ([471d8cb](https://github.com/mahdi-behnam/linkedaide/commit/471d8cb95760c94d4edfa1919daadf198ec5f617))
- **relay:** support connection action codes and handle edit and regenerate callbacks ([ee5489c](https://github.com/mahdi-behnam/linkedaide/commit/ee5489c3432167db150833bba86d9ea067f11e31))
- **safety:** wire state store into circuit breaker checks and executor initialization ([9d71db0](https://github.com/mahdi-behnam/linkedaide/commit/9d71db0df46a214db456e04c7f127c090f7cf9db))
- **scraper:** Enhance and fix DOM selectors for different actions ([444f735](https://github.com/mahdi-behnam/linkedaide/commit/444f735db74868c7f442febf9cecc6e8bf0543b1))
- **security:** guarantee cleanup of temporary unencrypted session files ([ba2d435](https://github.com/mahdi-behnam/linkedaide/commit/ba2d435929e54c828503844b9e765bc82e36ee25))
- **telegram:** track and advance update offset during polling ([8d1acce](https://github.com/mahdi-behnam/linkedaide/commit/8d1accefc2341da5d9a6e283b65ea0ec352f4b04))
- **types:** resolve python static type checking errors across codebase ([ab6f8e1](https://github.com/mahdi-behnam/linkedaide/commit/ab6f8e1c6cf27f6ac49575b505a1725138dde13d))

### Code Refactoring

- **architecture:** decompose monolithic modules into focused handlers and components ([eecdb47](https://github.com/mahdi-behnam/linkedaide/commit/eecdb47258bd96ca454c25ddeb29adab0705d9c8))
- decompose monolithic modules into focused submodules ([f6b445f](https://github.com/mahdi-behnam/linkedaide/commit/f6b445f90c24003485374060fe6b7159d3648937))
- **desktop:** align UI design with Apple Human Interface Guidelines and macOS design system ([c97f41a](https://github.com/mahdi-behnam/linkedaide/commit/c97f41ab819eb7d2a44223e293cff9cdf0949a36))
- **desktop:** eliminate dummy fallback data and implement standard empty states ([a64b315](https://github.com/mahdi-behnam/linkedaide/commit/a64b3151ab7e76ccf5ab63309d04031125c7f676))
- **desktop:** eliminate redundant status labels and copy across UI ([ddc0a39](https://github.com/mahdi-behnam/linkedaide/commit/ddc0a3922b664ab3650efc44f941c6a11634d6f0))
- **desktop:** remove dashboard health check button and sidebar edge sync widget ([f983010](https://github.com/mahdi-behnam/linkedaide/commit/f983010ece85332e43080d49cc253dc4388ace66))
- **desktop:** streamline status indicators and badges to native macOS typography ([e53873f](https://github.com/mahdi-behnam/linkedaide/commit/e53873ff393f4fd42981321393a5636b821e1a0f))
- **desktop:** style unsaved changes dock as rounded rectangle without pulsing dot ([85c0ef1](https://github.com/mahdi-behnam/linkedaide/commit/85c0ef14f81860461fee43a535714eb5d4ffa7bd))
- **desktop:** switch to Apple-style toggles and theme-adaptive picker icons ([53a9f22](https://github.com/mahdi-behnam/linkedaide/commit/53a9f2281f65db69ffab26197da501e3f7742ede))
- **graphs:** remove deprecated procedural thread monitor module in favor of thread graph ([ccb4f2a](https://github.com/mahdi-behnam/linkedaide/commit/ccb4f2a6e9f5272f4d1f25e958e719e69f61ae49))
- **tests:** rename test files for clarity and consistency ([d37ba34](https://github.com/mahdi-behnam/linkedaide/commit/d37ba34d05ef3ebc9968eda120cdd49d05559523))

### Performance Improvements

- **desktop:** code-split view components with dynamic imports and suspense ([b1e071e](https://github.com/mahdi-behnam/linkedaide/commit/b1e071ec0fcbb65fb304dbd377de81c31c9c9ab4))
- **relay:** add secondary message index for constant-time telegram reply lookups ([84cb9ab](https://github.com/mahdi-behnam/linkedaide/commit/84cb9abfa99026e241141345d4f8d6a2b0448b49))

### Documentation

- add comprehensive public documentation suite ([c14386e](https://github.com/mahdi-behnam/linkedaide/commit/c14386e24e9ac67bf64f1ec3ed918533082001c0))
- **agents:** add operating rules and conventions ([7e75f65](https://github.com/mahdi-behnam/linkedaide/commit/7e75f65ae93f441fa8ef0dd5cf1e92daaf821197))
- **agents:** require commit body description for non-trivial changes ([c81869d](https://github.com/mahdi-behnam/linkedaide/commit/c81869d866657996f53241833136a19e4ac2d19f))
- **config:** synchronize .env.example and document advanced subsystems in README ([e0a555f](https://github.com/mahdi-behnam/linkedaide/commit/e0a555fe674a41ba3f7b87ffe6214d56559c1afc))
- **desktop:** document Desktop App launch instructions and day-to-day operational workflow ([764fb1b](https://github.com/mahdi-behnam/linkedaide/commit/764fb1b8e12da4addc5052dcaf351a1472904b99))
- **desktop:** guide users to standalone downloads and document source builds ([ed6aa71](https://github.com/mahdi-behnam/linkedaide/commit/ed6aa71c8a2eec90877b68cf1ddbed516adf6e27))
- **license:** add MIT license ([bc4be4b](https://github.com/mahdi-behnam/linkedaide/commit/bc4be4baa7474af529f67024971c7fe381f57c5c))
- **readme:** clarify capabilities, fix onboarding setup, and add CLI poll and ideate commands ([84618fa](https://github.com/mahdi-behnam/linkedaide/commit/84618fa040f122be06e22d568260fde21e5c3625))
- **relay:** document NVIDIA_NIM_API_KEY secret for worker draft rewrites ([bbcf23a](https://github.com/mahdi-behnam/linkedaide/commit/bbcf23ac98783aee93077ebf471d52375d7ed1c6))
- **setup:** document Cloudflare KV and R2 provisioning steps before worker deployment ([632fa08](https://github.com/mahdi-behnam/linkedaide/commit/632fa0891be2639e2c7d260d5ceae7a8648b83e2))
- **setup:** document Cloudflare KV secrets required for GitHub Actions ([f0c58a2](https://github.com/mahdi-behnam/linkedaide/commit/f0c58a2a6f607d6bdea57a1599deace8a26d3cc5))
- **setup:** enhance setup guide with KV ID instructions and R2 dashboard activation details ([64f9394](https://github.com/mahdi-behnam/linkedaide/commit/64f93941edd40a1a8f684a0db50bcc0aa85f83b4))
- **setup:** make Cloudflare R2 optional by default and document zero-card setup ([8d41787](https://github.com/mahdi-behnam/linkedaide/commit/8d417876d2edce94f899489f612457f1feffe76b))
- update configuration references, directory tree, and cli documentation ([c35ceab](https://github.com/mahdi-behnam/linkedaide/commit/c35ceab0f483b778ac87c8c132a36eefe47a5733))
- update system architecture and configuration guide with recent features ([83b96a2](https://github.com/mahdi-behnam/linkedaide/commit/83b96a2c9cb32e1644c911f8b976a07064398057))

### Tests

- **adversarial:** add adversarial challenge test suites for reliability hardening ([407cfe9](https://github.com/mahdi-behnam/linkedaide/commit/407cfe951ec6cc94b49780f86b70f5b9ef6d4cd6))
- **browser:** add unit and integration tests for targeted scouting ([5fbbedd](https://github.com/mahdi-behnam/linkedaide/commit/5fbbedd53651f4ec0c9fe1781f0b52ee03cb6507))
- **coverage:** expand test suites across orchestration flows and error paths to exceed 90% coverage ([982ef3a](https://github.com/mahdi-behnam/linkedaide/commit/982ef3a15a8e1e6b66101e97f2a8e8ac3f9d1d65))
- **desktop:** wrap analytics refresh event in act to eliminate test warning ([e350cbb](https://github.com/mahdi-behnam/linkedaide/commit/e350cbb250b9c6f9d0fd00c5615e2fd5dbe8f66b))
- **graphs:** add topology invariant unit tests ([f1b21b0](https://github.com/mahdi-behnam/linkedaide/commit/f1b21b0d170e9edd27ae3740884bdc208dafef5c))
- **graphs:** add unit tests for ideation graph and orchestration ([fb32812](https://github.com/mahdi-behnam/linkedaide/commit/fb32812775089678320967e54778b9ccbe27ef50))
- **orchestration:** fix date rollover in command handler status test ([f0d8df8](https://github.com/mahdi-behnam/linkedaide/commit/f0d8df85751ea55d680e1f0c949929ebaf89dc1c))
- **relay:** fix execution context typing in r2 tests and add typecheck script ([81123ec](https://github.com/mahdi-behnam/linkedaide/commit/81123ecbfbef6e547b8ec8a1d6203a2a816e2096))
- **state:** mark git pre-receive test hooks executable ([0bad2dd](https://github.com/mahdi-behnam/linkedaide/commit/0bad2dd4252630fe63c7009830d42b5520a6c5ce))
- **state:** mark git pre-receive test hooks executable ([b65f4a3](https://github.com/mahdi-behnam/linkedaide/commit/b65f4a3fb73d26c5cc977192b5c575cbbbfef5c3))
- **telegram:** add comprehensive unit and integration tests for draft editing and command router ([ce8f4d9](https://github.com/mahdi-behnam/linkedaide/commit/ce8f4d9bf27de84c8b1857a78ec73f9bbecf3b17))
- **workflow:** add comprehensive test suites for expired pruning, organic reactions, and engagement styles ([a06c6da](https://github.com/mahdi-behnam/linkedaide/commit/a06c6da6fa54426ee0e6534f242da0e5255e1707))

### Continuous Integration

- **actions:** add CI and automation workflows ([9e97795](https://github.com/mahdi-behnam/linkedaide/commit/9e9779503d676dab9368fe6daf760ccd9b85048e))
- **actions:** add max connections per day limit to workflows ([a91c4dd](https://github.com/mahdi-behnam/linkedaide/commit/a91c4dd49613c224017580b496a9a68e4b7be4d2))
- **actions:** add scheduled thread reply monitoring workflow ([b04b845](https://github.com/mahdi-behnam/linkedaide/commit/b04b845a9a792d67378317438add9e2061f2763b))
- **actions:** align artifact retention, ideation persona, and desktop release flags ([0a14540](https://github.com/mahdi-behnam/linkedaide/commit/0a14540e45fd0e21182eaf3684385f77ca05fd21))
- **actions:** enforce bash shell for desktop releases and add electron build to ci ([c834084](https://github.com/mahdi-behnam/linkedaide/commit/c8340842740d23c6d956f22427c88b56cc621ade))
- **actions:** expose target urls and hashtags in scout workflow ([950e6a2](https://github.com/mahdi-behnam/linkedaide/commit/950e6a26875fd027d761db0ce2dec473b998840f))
- **actions:** inject worker url and api secret for r2 audit screenshots ([73bbe43](https://github.com/mahdi-behnam/linkedaide/commit/73bbe4398231a0f29cba2198f02e3b51d57b2b21))
- **actions:** pass session encryption key to execution steps for cookie keepalive ([5421d33](https://github.com/mahdi-behnam/linkedaide/commit/5421d330f938737cb86043e3519f072c2855c882))
- **workflows:** add type check and test jobs for worker and desktop app ([d5cdb03](https://github.com/mahdi-behnam/linkedaide/commit/d5cdb03c1c7d2f7dd7e2789e5dcdccae61f4ae18))
