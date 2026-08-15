/* auth-terminal.js - the login / onboarding / first-view terminal.
   Generated from the design source (henneth-login-terminal-wake6-v4.html) by
   scratchpad/gen_auth_js.py: the markup and the whole animation/onboarding script
   are copied verbatim, only reopened as a mountable function so the desk can host
   them instead of owning <body>. Styles live in auth-terminal.css.

   This file now owns the design: keep the markup and animation identical to the design
   source, and keep every host integration behind `hooks` (onSubmit / onTabChange / onEnterDesk)
   so app.js can supply real auth and real onboarding persistence without touching the scene.
   Supabase wiring lives in app.js and attaches to the returned handles. */
(function () {
  "use strict";

  var HN_MARKUP = `<div class="page">

  <nav class="nav">
    <a href="#" class="nav-brand"><img class="nav-brand-mark" src="logo-terminal.svg" alt="" width="535" height="472" decoding="async">HENNETH<small>&nbsp;DESK</small></a>
    <div class="nav-right">
      <div class="nav-chip">Research · Not Advice</div>
      <a href="https://henneth.app/" class="nav-back">← Back to site</a>
    </div>
  </nav>

  <div class="split">

    <div class="left">
      <div class="form-wrap" id="formWrap">
        <p class="eyebrow">Account</p>
        <h1 class="headline" id="headline">Sign In To Henneth Desk</h1>
        <p class="sub" id="subcopy">Both sides of the argument, on every PSX stock.</p>

        <div class="tabs" role="tablist" aria-label="Account access mode">
          <button type="button" class="tab" id="tabSignin" role="tab" aria-selected="true">Sign In</button>
          <button type="button" class="tab" id="tabCreate" role="tab" aria-selected="false">Create Account</button>
        </div>

        <div class="field" id="nameField" hidden>
          <label class="field-label" for="nameInput">Full name</label>
          <input type="text" id="nameInput" placeholder="your name" autocomplete="name" />
          <p class="field-err" id="errName"></p>
        </div>

        <div class="field">
          <label class="field-label" for="emailInput">Email</label>
          <input type="email" id="emailInput" placeholder="you@example.com" autocomplete="email" required aria-required="true" />
          <p class="field-err" id="errEmail"></p>
        </div>

        <div class="field">
          <label class="field-label" for="pwInput">Password</label>
          <div class="pw-wrap">
            <input type="password" id="pwInput" placeholder="your password" autocomplete="current-password" required aria-required="true" />
            <button type="button" class="pw-toggle" id="pwToggle">Show</button>
          </div>
          <p class="field-err" id="errPw"></p>
        </div>

        <p class="forgot-line" id="forgotLine"><button type="button" class="switch-link" id="authForgot">Forgot your password?</button></p>

        <div class="meter" id="meter" aria-hidden="true">
          <i id="m0"></i><i id="m1"></i><i id="m2"></i><i id="m3"></i>
        </div>
        <p class="meter-copy" id="meterCopy">Longer beats complicated. Three unrelated words are stronger than <strong>P@ssw0rd!</strong> and easier to remember.</p>

        <div class="capbox" id="capBox"></div>

        <button type="button" class="odo-btn" id="ctaBtn">
          <span class="odo-face a" id="ctaA">Sign In</span>
          <span class="odo-face b" id="ctaB">Sign In</span>
        </button>

        <p class="auth-msg" id="authMsg" role="status" aria-live="polite" hidden></p>

        <p class="switch-line">
          <span id="switchPrompt">Don't have an account yet?</span>
          <button type="button" class="switch-link" id="switchLink">Create one</button>
        </p>

        <div class="legal">
          <p>Henneth Desk is a research &amp; analytics tool — not an investment adviser. Nothing here is personalized advice. By continuing you agree to the <a href="#">Terms</a>, <a href="#">Privacy Policy</a> and <a href="#">Risk Disclosure</a>.</p>
        </div>
      </div>

      <section class="onboarding-shell" id="onboardingShell" hidden aria-live="polite">
        <div class="onboarding-top">
          <div>
            <p class="onboarding-kicker" id="onboardingKicker">Desk calibration</p>
            <h1 class="onboarding-title" id="onboardingTitle">Let’s prepare your desk around how you actually invest.</h1>
          </div>
          <div class="onboarding-progress" id="onboardingProgress"><strong>1 / 4</strong>Calibrating your desk</div>
        </div>
        <div class="onboarding-track" aria-hidden="true"><span id="onboardingTrackFill"></span></div>
        <p class="onboarding-copy" id="onboardingCopy">Four quick choices will tune your daily brief, watchlist, screeners, lessons, and market signals. You can change anything later.</p>

        <div class="onboarding-step" id="onboardingStep"></div>

        <div class="onboarding-actions" id="onboardingActions">
          <div class="onboarding-links">
            <button type="button" class="onboarding-link" id="onboardingSkip">Skip for now</button>
            <button type="button" class="onboarding-link" id="onboardingSave">Save and continue later</button>
            <button type="button" class="onboarding-link" id="onboardingKnow">I already know what I want</button>
          </div>
          <button type="button" class="onboarding-action ghost" id="onboardingBack" hidden>Back</button>
          <button type="button" class="onboarding-action primary" id="onboardingNext">Open path</button>
        </div>
      </section>

      <section class="today-shell" id="todayShell" hidden aria-live="polite">
        <div class="today-header">
          <div>
            <p class="onboarding-kicker">Your first desk view</p>
            <h2 id="todayTitle">Good morning. Your desk is ready.</h2>
          </div>
          <div><button type="button" class="onboarding-link" id="todayResume" hidden>Resume calibration</button><span class="today-date" id="todayDate">Today · PSX</span></div>
        </div>
        <div class="today-grid" id="todayGrid">
          <article class="today-card wide" tabindex="0">
            <p class="card-label">Your brief</p>
            <h3 id="todayBriefTitle">Balanced context, then the names worth a closer look.</h3>
            <p id="todayBriefCopy">We’ll put the market tone first, then explain what it changes for your radar.</p>
            <a href="#" class="card-action">Open today’s brief →</a>
          </article>
          <article class="today-card" tabindex="0">
            <p class="card-label">Your radar</p>
            <h3 id="todayRadarTitle">A focused starting set</h3>
            <p id="todayRadarCopy">Choose sectors or names and we’ll keep them close to the desk.</p>
            <a href="#" class="card-action">Open radar →</a>
          </article>
          <article class="today-card" tabindex="0">
            <p class="card-label">Your next move</p>
            <h3 id="todayNextTitle">Save one name from Today.</h3>
            <p id="todayNextCopy">One meaningful action is enough to make this desk yours.</p>
            <a href="#" class="card-action">Start here →</a>
          </article>
          <article class="today-card span" tabindex="0">
            <p class="card-label">Your next lesson</p>
            <h3 id="todayLessonTitle">The balance sheet, line by line.</h3>
            <p id="todayLessonCopy">Eight minutes, tied to the lens you just picked. Skippable, and it remembers where you stopped.</p>
            <a href="#" class="card-action">Open the lesson →</a>
          </article>
        </div>
        <details class="checklist" id="checklist" open>
          <summary>Keep the momentum · 0 of 7 complete</summary>
          <label class="check-row"><input type="checkbox" data-check="stock" /> Add your first stock</label>
          <label class="check-row"><input type="checkbox" data-check="brief" /> Review today’s personalized brief</label>
          <label class="check-row"><input type="checkbox" data-check="company" /> Open one company or sector page</label>
          <label class="check-row"><input type="checkbox" data-check="screener" /> Save a screener</label>
          <label class="check-row"><input type="checkbox" data-check="ask" /> Ask the desk one question</label>
          <label class="check-row"><input type="checkbox" data-check="lesson" /> Complete your first lesson</label>
          <label class="check-row"><input type="checkbox" data-check="chart" /> Optional: confirm chart preferences</label>
        </details>
        <div class="today-enter"><button type="button" class="onboarding-action primary" id="enterDesk">Enter the desk →</button></div>
      </section>
    </div>

    <div class="right" id="rightPanel">
      <div class="right-glow"></div>
      <div class="descent-scene" id="descentScene" aria-hidden="true">
        <div class="descent-aperture" id="descentAperture"><span></span></div>
        <div class="descent-layer descent-far" id="descentFar"><i></i><i></i><i></i><i></i></div>
        <div class="descent-layer descent-mid" id="descentMid"><i></i><i></i><i></i><i></i></div>
        <div class="descent-layer descent-foreground" id="descentForeground"><i></i><i></i><i></i></div>
        <div class="conflict-field" id="conflictField"><span class="conflict-bull">BULL PATH</span><span class="conflict-bear">BEAR PATH</span><b>UNRESOLVED</b></div>
        <div class="descent-label" id="descentLabel">SURFACE MAP INCOMPLETE</div>
        <div class="descent-depth" id="depthReadout">DEPTH 00 · SURFACE</div>
      </div>
      <div class="right-parallax" id="parallaxLayer">

        <svg class="universe-svg" id="universeSvg" viewBox="0 0 1000 900" preserveAspectRatio="xMidYMid slice">
          <g id="universeGroup">
          <!-- ACT 1: broken/unresolved line fragments (dim, fast, sparse) -->
          <line class="hn-edge hn-act1" x1="502.5" y1="576.9" x2="487.3" y2="590.2" stroke="rgba(255,255,255,.22)" stroke-width="1" style="opacity:.3;stroke-dasharray:20.2;stroke-dashoffset:20.2;animation:hnDraw .5s cubic-bezier(.16,1,.3,1) 0.15s both"></line>
          <line class="hn-edge hn-act1" x1="428.9" y1="130.7" x2="454.2" y2="103.6" stroke="rgba(255,255,255,.22)" stroke-width="1" style="opacity:.3;stroke-dasharray:37.1;stroke-dashoffset:37.1;animation:hnDraw .5s cubic-bezier(.16,1,.3,1) 0.26s both"></line>
          <line class="hn-edge hn-act1" x1="425.6" y1="721.6" x2="405.7" y2="766.2" stroke="rgba(255,255,255,.22)" stroke-width="1" style="opacity:.3;stroke-dasharray:48.9;stroke-dashoffset:48.9;animation:hnDraw .5s cubic-bezier(.16,1,.3,1) 0.37s both"></line>
          <line class="hn-edge hn-act1" x1="591.2" y1="358.3" x2="603.5" y2="416.7" stroke="rgba(255,255,255,.22)" stroke-width="1" style="opacity:.3;stroke-dasharray:59.8;stroke-dashoffset:59.8;animation:hnDraw .5s cubic-bezier(.16,1,.3,1) 0.48s both"></line>
          <line class="hn-edge hn-act1" x1="155.8" y1="330.5" x2="223.6" y2="346.7" stroke="rgba(255,255,255,.22)" stroke-width="1" style="opacity:.3;stroke-dasharray:69.7;stroke-dashoffset:69.7;animation:hnDraw .5s cubic-bezier(.16,1,.3,1) 0.59s both"></line>
          <line class="hn-edge hn-act1" x1="712.2" y1="296.3" x2="751.4" y2="238.3" stroke="rgba(255,255,255,.22)" stroke-width="1" style="opacity:.3;stroke-dasharray:70.0;stroke-dashoffset:70.0;animation:hnDraw .5s cubic-bezier(.16,1,.3,1) 0.70s both"></line>

          <!-- ACT 2: structured market map assembling from the fragments -->
          <line class="hn-edge" x1="901.6" y1="442.1" x2="932.2" y2="514.4" stroke="#00a884" stroke-width="1" data-syms="MARI,NBP" style="opacity:.34;stroke-dasharray:78.5;stroke-dashoffset:78.5;animation-delay:1.350s"></line>
          <line class="hn-edge" x1="175.8" y1="411.4" x2="223.6" y2="346.7" stroke="#00a884" stroke-width="1" data-syms="PPL" style="opacity:.34;stroke-dasharray:80.5;stroke-dashoffset:80.5;animation-delay:1.395s"></line>
          <line class="hn-edge" x1="155.8" y1="330.5" x2="175.8" y2="411.4" stroke="#00a884" stroke-width="1" data-syms="FFC,PPL" style="opacity:.34;stroke-dasharray:83.3;stroke-dashoffset:83.3;animation-delay:1.440s"></line>
          <line class="hn-edge" x1="304.6" y1="760.1" x2="405.7" y2="766.2" stroke="rgba(255,255,255,.12)" stroke-width="1" style="opacity:.16;stroke-dasharray:101.3;stroke-dashoffset:101.3;animation-delay:1.485s"></line>
          <line class="hn-edge" x1="568.0" y1="723.4" x2="622.2" y2="813.3" stroke="#00a884" stroke-width="1" data-syms="ENGROH" style="opacity:.34;stroke-dasharray:105.0;stroke-dashoffset:105.0;animation-delay:1.530s"></line>
          <line class="hn-edge" x1="788.9" y1="87.4" x2="892.2" y2="49.6" stroke="#00a884" stroke-width="1" data-syms="EFERT" style="opacity:.34;stroke-dasharray:110.0;stroke-dashoffset:110.0;animation-delay:1.575s"></line>
          <line class="hn-edge" x1="425.6" y1="721.6" x2="304.6" y2="760.1" stroke="#00a884" stroke-width="1" data-syms="UBL" style="opacity:.34;stroke-dasharray:127.0;stroke-dashoffset:127.0;animation-delay:1.620s"></line>
          <line class="hn-edge" x1="901.6" y1="442.1" x2="797.9" y2="518.0" stroke="#00a884" stroke-width="1" data-syms="MARI" style="opacity:.34;stroke-dasharray:128.5;stroke-dashoffset:128.5;animation-delay:1.665s"></line>
          <line class="hn-edge" x1="325.5" y1="261.6" x2="223.6" y2="346.7" stroke="rgba(255,255,255,.12)" stroke-width="1" style="opacity:.16;stroke-dasharray:132.8;stroke-dashoffset:132.8;animation-delay:1.710s"></line>
          <line class="hn-edge" x1="932.2" y1="514.4" x2="797.9" y2="518.0" stroke="#00a884" stroke-width="1" data-syms="NBP" style="opacity:.34;stroke-dasharray:134.3;stroke-dashoffset:134.3;animation-delay:1.755s"></line>
          <line class="hn-edge" x1="549.2" y1="200.0" x2="454.2" y2="103.6" stroke="rgba(255,255,255,.12)" stroke-width="1" style="opacity:.16;stroke-dasharray:135.4;stroke-dashoffset:135.4;animation-delay:1.800s"></line>
          <line class="hn-edge" x1="712.2" y1="296.3" x2="591.2" y2="358.3" stroke="#00a884" stroke-width="1" data-syms="MEBL,HBL" style="opacity:.34;stroke-dasharray:136.0;stroke-dashoffset:136.0;animation-delay:1.845s"></line>
          <line class="hn-edge" x1="428.9" y1="130.7" x2="549.2" y2="200.0" stroke="#00a884" stroke-width="1" data-syms="BAHL" style="opacity:.34;stroke-dasharray:138.8;stroke-dashoffset:138.8;animation-delay:1.890s"></line>
          <line class="hn-edge" x1="568.0" y1="723.4" x2="425.6" y2="721.6" stroke="#00a884" stroke-width="1" data-syms="ENGROH,UBL" style="opacity:.34;stroke-dasharray:142.4;stroke-dashoffset:142.4;animation-delay:1.935s"></line>
          <line class="hn-edge" x1="487.3" y1="590.2" x2="425.6" y2="721.6" stroke="#00a884" stroke-width="1" data-syms="UBL" style="opacity:.34;stroke-dasharray:145.1;stroke-dashoffset:145.1;animation-delay:1.980s"></line>
          <line class="hn-edge" x1="753.0" y1="661.1" x2="797.9" y2="518.0" stroke="rgba(255,255,255,.12)" stroke-width="1" style="opacity:.16;stroke-dasharray:149.9;stroke-dashoffset:149.9;animation-delay:2.025s"></line>
          <line class="hn-edge" x1="905.2" y1="235.9" x2="751.4" y2="238.3" stroke="#00a884" stroke-width="1" data-syms="HUBC,MCB" style="opacity:.34;stroke-dasharray:153.8;stroke-dashoffset:153.8;animation-delay:2.070s"></line>
          <line class="hn-edge" x1="788.9" y1="87.4" x2="751.4" y2="238.3" stroke="#00a884" stroke-width="1" data-syms="EFERT,MCB" style="opacity:.34;stroke-dasharray:155.5;stroke-dashoffset:155.5;animation-delay:2.115s"></line>
          <line class="hn-edge" x1="502.5" y1="576.9" x2="568.0" y2="723.4" stroke="#00a884" stroke-width="1" data-syms="SYS,ENGROH" style="opacity:.34;stroke-dasharray:160.5;stroke-dashoffset:160.5;animation-delay:2.160s"></line>
          <line class="hn-edge" x1="603.5" y1="416.7" x2="712.2" y2="296.3" stroke="#00a884" stroke-width="1" data-syms="MEBL" style="opacity:.34;stroke-dasharray:162.2;stroke-dashoffset:162.2;animation-delay:2.205s"></line>
          <line class="hn-edge" x1="325.5" y1="261.6" x2="428.9" y2="130.7" stroke="#00a884" stroke-width="1" data-syms="BAHL" style="opacity:.34;stroke-dasharray:166.8;stroke-dashoffset:166.8;animation-delay:2.250s"></line>
          <line class="hn-edge" x1="153.1" y1="577.5" x2="175.8" y2="411.4" stroke="#00a884" stroke-width="1" data-syms="OGDC,PPL" style="opacity:.34;stroke-dasharray:167.6;stroke-dashoffset:167.6;animation-delay:2.295s"></line>
          <line class="hn-edge" x1="153.1" y1="577.5" x2="313.5" y2="521.2" stroke="#00a884" stroke-width="1" data-syms="OGDC,LUCK" style="opacity:.34;stroke-dasharray:170.0;stroke-dashoffset:170.0;animation-delay:2.340s"></line>
          <line class="hn-edge" x1="313.5" y1="521.2" x2="175.8" y2="411.4" stroke="#00a884" stroke-width="1" data-syms="LUCK,PPL" style="opacity:.34;stroke-dasharray:176.1;stroke-dashoffset:176.1;animation-delay:2.385s"></line>
          <line class="hn-edge" x1="905.2" y1="235.9" x2="892.2" y2="49.6" stroke="#00a884" stroke-width="1" data-syms="HUBC" style="opacity:.34;stroke-dasharray:186.8;stroke-dashoffset:186.8;animation-delay:2.430s"></line>
          <line class="hn-edge" x1="753.0" y1="661.1" x2="568.0" y2="723.4" stroke="#00a884" stroke-width="1" data-syms="ENGROH" style="opacity:.34;stroke-dasharray:195.1;stroke-dashoffset:195.1;animation-delay:2.475s"></line>
          <line class="hn-edge" x1="622.2" y1="813.3" x2="753.0" y2="661.1" stroke="rgba(255,255,255,.12)" stroke-width="1" style="opacity:.16;stroke-dasharray:200.7;stroke-dashoffset:200.7;animation-delay:2.520s"></line>

          <!-- ACT 2: board nodes lighting up as evidence resolves -->
          <circle id="node-FFC" class="hn-node hn-node-lit" data-sym="FFC" cx="155.8" cy="330.5" r="5" fill="#00a884" style="animation-delay:1.500s;filter:drop-shadow(0 0 4px rgba(0,168,132,.5))"></circle>
          <circle id="node-UBL" class="hn-node hn-node-lit" data-sym="UBL" cx="425.6" cy="721.6" r="5" fill="#e34b2f" style="animation-delay:1.550s;filter:drop-shadow(0 0 4px rgba(227,75,47,.45))"></circle>
          <circle id="node-ENGROH" class="hn-node hn-node-lit" data-sym="ENGROH" cx="568.0" cy="723.4" r="5" fill="#00a884" style="animation-delay:1.600s;filter:drop-shadow(0 0 4px rgba(0,168,132,.5))"></circle>
          <circle id="node-MEBL" class="hn-node hn-node-lit" data-sym="MEBL" cx="712.2" cy="296.3" r="5" fill="#e34b2f" style="animation-delay:1.650s;filter:drop-shadow(0 0 4px rgba(227,75,47,.45))"></circle>
          <circle id="node-HUBC" class="hn-node hn-node-lit" data-sym="HUBC" cx="905.2" cy="235.9" r="5" fill="#00a884" style="animation-delay:1.700s;filter:drop-shadow(0 0 4px rgba(0,168,132,.5))"></circle>
          <circle id="node-OGDC" class="hn-node hn-node-lit" data-sym="OGDC" cx="153.1" cy="577.5" r="5" fill="#00a884" style="animation-delay:1.750s;filter:drop-shadow(0 0 4px rgba(0,168,132,.5))"></circle>
          <circle id="node-LUCK" class="hn-node hn-node-lit" data-sym="LUCK" cx="313.5" cy="521.2" r="5" fill="#e34b2f" style="animation-delay:1.800s;filter:drop-shadow(0 0 4px rgba(227,75,47,.45))"></circle>
          <circle id="node-HBL" class="hn-node hn-node-lit" data-sym="HBL" cx="591.2" cy="358.3" r="5" fill="#e34b2f" style="animation-delay:1.850s;filter:drop-shadow(0 0 4px rgba(227,75,47,.45))"></circle>
          <circle id="node-MCB" class="hn-node hn-node-lit" data-sym="MCB" cx="751.4" cy="238.3" r="5" fill="#00a884" style="animation-delay:1.900s;filter:drop-shadow(0 0 4px rgba(0,168,132,.5))"></circle>
          <circle id="node-MARI" class="hn-node hn-node-lit" data-sym="MARI" cx="901.6" cy="442.1" r="5" fill="#00a884" style="animation-delay:1.950s;filter:drop-shadow(0 0 4px rgba(0,168,132,.5))"></circle>
          <circle id="node-PPL" class="hn-node hn-node-lit" data-sym="PPL" cx="175.8" cy="411.4" r="5" fill="#e34b2f" style="animation-delay:2.000s;filter:drop-shadow(0 0 4px rgba(227,75,47,.45))"></circle>
          <circle id="node-BAHL" class="hn-node hn-node-lit" data-sym="BAHL" cx="428.9" cy="130.7" r="5" fill="#00a884" style="animation-delay:2.050s;filter:drop-shadow(0 0 4px rgba(0,168,132,.5))"></circle>
          <circle id="node-SYS" class="hn-node hn-node-lit" data-sym="SYS" cx="502.5" cy="576.9" r="5" fill="#00a884" style="animation-delay:2.100s;filter:drop-shadow(0 0 4px rgba(0,168,132,.5))"></circle>
          <circle id="node-EFERT" class="hn-node hn-node-lit" data-sym="EFERT" cx="788.9" cy="87.4" r="5" fill="#e34b2f" style="animation-delay:2.150s;filter:drop-shadow(0 0 4px rgba(227,75,47,.45))"></circle>
          <circle id="node-NBP" class="hn-node hn-node-lit" data-sym="NBP" cx="932.2" cy="514.4" r="5" fill="#00a884" style="animation-delay:2.200s;filter:drop-shadow(0 0 4px rgba(0,168,132,.5))"></circle>
          <circle class="hn-node" cx="603.5" cy="416.7" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.250s;opacity:.32"></circle>
          <circle class="hn-node" cx="549.2" cy="200.0" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.300s;opacity:.32"></circle>
          <circle class="hn-node" cx="487.3" cy="590.2" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.350s;opacity:.32"></circle>
          <circle class="hn-node" cx="892.2" cy="49.6" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.400s;opacity:.32"></circle>
          <circle class="hn-node" cx="325.5" cy="261.6" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.450s;opacity:.32"></circle>
          <circle class="hn-node" cx="223.6" cy="346.7" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.500s;opacity:.32"></circle>
          <circle class="hn-node" cx="622.2" cy="813.3" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.550s;opacity:.32"></circle>
          <circle class="hn-node" cx="797.9" cy="518.0" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.600s;opacity:.32"></circle>
          <circle class="hn-node" cx="45.9" cy="70.0" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.650s;opacity:.32"></circle>
          <circle class="hn-node" cx="753.0" cy="661.1" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.700s;opacity:.32"></circle>
          <circle class="hn-node" cx="304.6" cy="760.1" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.750s;opacity:.32"></circle>
          <circle class="hn-node" cx="454.2" cy="103.6" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.800s;opacity:.32"></circle>
          <circle class="hn-node" cx="405.7" cy="766.2" r="2" fill="rgba(255,255,255,.26)" style="animation-delay:2.850s;opacity:.32"></circle>

          <!-- ACT 2: labels resolving -->
          <text id="label-FFC" class="hn-label" data-sym="FFC" x="165.8" y="334.5" text-anchor="start" style="animation-delay:1.900s">FFC</text>
          <text id="label-UBL" class="hn-label" data-sym="UBL" x="435.6" y="725.6" text-anchor="start" style="animation-delay:1.960s">UBL</text>
          <text id="label-ENGROH" class="hn-label" data-sym="ENGROH" x="558.0" y="727.4" text-anchor="end" style="animation-delay:2.020s">ENGROH</text>
          <text id="label-MEBL" class="hn-label" data-sym="MEBL" x="702.2" y="300.3" text-anchor="end" style="animation-delay:2.080s">MEBL</text>
          <text id="label-HUBC" class="hn-label" data-sym="HUBC" x="895.2" y="239.9" text-anchor="end" style="animation-delay:2.140s">HUBC</text>
          <text id="label-OGDC" class="hn-label" data-sym="OGDC" x="163.1" y="581.5" text-anchor="start" style="animation-delay:2.200s">OGDC</text>
          <text id="label-LUCK" class="hn-label" data-sym="LUCK" x="323.5" y="525.2" text-anchor="start" style="animation-delay:2.260s">LUCK</text>
          <text id="label-HBL" class="hn-label" data-sym="HBL" x="581.2" y="362.3" text-anchor="end" style="animation-delay:2.320s">HBL</text>
          <text id="label-MCB" class="hn-label" data-sym="MCB" x="741.4" y="242.3" text-anchor="end" style="animation-delay:2.380s">MCB</text>
          <text id="label-MARI" class="hn-label" data-sym="MARI" x="891.6" y="446.1" text-anchor="end" style="animation-delay:2.440s">MARI</text>
          <text id="label-PPL" class="hn-label" data-sym="PPL" x="185.8" y="415.4" text-anchor="start" style="animation-delay:2.500s">PPL</text>
          <text id="label-BAHL" class="hn-label" data-sym="BAHL" x="438.9" y="134.7" text-anchor="start" style="animation-delay:2.560s">BAHL</text>
          <text id="label-SYS" class="hn-label" data-sym="SYS" x="512.5" y="580.9" text-anchor="start" style="animation-delay:2.620s">SYS</text>
          <text id="label-EFERT" class="hn-label" data-sym="EFERT" x="778.9" y="91.4" text-anchor="end" style="animation-delay:2.680s">EFERT</text>
          <text id="label-NBP" class="hn-label" data-sym="NBP" x="922.2" y="518.4" text-anchor="end" style="animation-delay:2.740s">NBP</text>

          <!-- idle pulse travellers, rare and low-opacity, only after story settles -->
          <circle class="hn-pulse" r="2" fill="#00a884" style="offset-path:path('M 901.6 442.1 L 932.2 514.4');animation-delay:5.20s"></circle>
          <circle class="hn-pulse" r="2" fill="#00a884" style="offset-path:path('M 932.2 514.4 L 797.9 518.0');animation-delay:8.80s"></circle>
          <circle class="hn-pulse" r="2" fill="#00a884" style="offset-path:path('M 502.5 576.9 L 568.0 723.4');animation-delay:12.40s"></circle>
          </g>
        </svg>

        <div class="calibration-orbit" id="calibrationOrbit" aria-hidden="true"><span></span></div>

        <!-- ACT 1: raw evidence fragments -->
        <div class="evidence-layer" id="evidenceLayer">
          <div class="ev-frag ev-onboarding" data-evidence="value" style="top:9%; left:8%;"><span class="ev-tag">VALUE —</span><span class="ev-val">PENDING</span></div>
          <div class="ev-frag ev-onboarding" data-evidence="momentum" style="top:16%; left:62%;"><span class="ev-tag">MOMENTUM —</span><span class="ev-val">UNRESOLVED</span></div>
          <div class="ev-frag ev-onboarding" data-evidence="risk" style="top:34%; left:22%;"><span class="ev-tag">RISK —</span><span class="ev-val">UNRESOLVED</span></div>
          <div class="ev-frag ev-onboarding" data-evidence="dividend" style="top:46%; left:71%;"><span class="ev-tag">DIVIDEND —</span><span class="ev-val">4 METHODS</span></div>
          <div class="ev-frag ev-onboarding" data-evidence="earnings" style="top:62%; left:12%;"><span class="ev-tag">EARNINGS —</span><span class="ev-val">PENDING</span></div>
          <div class="ev-frag ev-onboarding" data-evidence="macro" style="top:73%; left:56%;"><span class="ev-tag">MACRO —</span><span class="ev-val">CONTEXT OPEN</span></div>
          <div class="ev-frag" style="top:9%; left:8%;"><span class="ev-tag">HEALTH —</span><span class="ev-val">PENDING</span></div>
          <div class="ev-frag" style="top:16%; left:62%;"><span class="ev-tag">REGIME —</span><span class="ev-val">UNRESOLVED</span></div>
          <div class="ev-frag" style="top:34%; left:22%;"><span class="ev-tag">RISK —</span><span class="ev-val">UNRESOLVED</span></div>
          <div class="ev-frag" style="top:46%; left:71%;"><span class="ev-tag">VALUE —</span><span class="ev-val">4 METHODS</span></div>
          <div class="ev-frag" style="top:62%; left:12%;"><span class="ev-tag">BREADTH —</span><span class="ev-val">PENDING</span></div>
          <div class="ev-frag" style="top:73%; left:56%;"><span class="ev-tag">GLOBAL TAPE —</span><span class="ev-val">CONTEXT OPEN</span></div>
          <div class="ev-frag" style="top:86%; left:26%; color:rgba(232,230,224,.4);">NOT ADVICE</div>
        </div>

        <!-- Market Path Status -->
        <div class="path-status">
          <div class="status-line" id="statusLine" aria-live="polite">Tracking the market&#8217;s path<span class="caret"></span></div>
          <div class="status-pct" id="statusPct" role="progressbar" aria-label="Terminal preparation progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">0%</div>
        </div>
        <div class="path-track"><div class="path-fill" id="pathFill"></div></div>

        <!-- rotating circular seal (completion mark) -->
        <div class="seal" id="seal">
          <svg viewBox="0 0 200 200">
            <g class="seal-ring" id="sealRing">
              <path id="sealPath" d="M 100,4 A 96,96 0 1 1 99.9,4" fill="none" />
              <text font-family="var(--mono)">
                <textPath id="sealTextPath" href="#sealPath" startOffset="0%"></textPath>
              </text>
            </g>
          </svg>
          <div class="seal-center"><span class="dot"></span></div>
        </div>

        <!-- board -->
        <div class="board board-transition" id="board">
          <div class="board-head">
            <div class="t1">Board</div>
            <div class="t2"><span class="live-dot"></span>Live Research</div>
          </div>
          <div class="grid5" id="tickerGrid">
            <div class="cell" data-sym="FFC"><div class="sym">FFC</div><div class="chg up" id="chg-FFC">+2.9%</div></div>
            <div class="cell" data-sym="UBL"><div class="sym">UBL</div><div class="chg down" id="chg-UBL">-1.3%</div></div>
            <div class="cell" data-sym="ENGROH"><div class="sym">ENGROH</div><div class="chg up" id="chg-ENGROH">+3.0%</div></div>
            <div class="cell" data-sym="MEBL"><div class="sym">MEBL</div><div class="chg down" id="chg-MEBL">-1.5%</div></div>
            <div class="cell" data-sym="HUBC"><div class="sym">HUBC</div><div class="chg up" id="chg-HUBC">+2.0%</div></div>
            <div class="cell" data-sym="OGDC"><div class="sym">OGDC</div><div class="chg up" id="chg-OGDC">+3.8%</div></div>
            <div class="cell" data-sym="LUCK"><div class="sym">LUCK</div><div class="chg down" id="chg-LUCK">-0.5%</div></div>
            <div class="cell" data-sym="HBL"><div class="sym">HBL</div><div class="chg down" id="chg-HBL">-1.7%</div></div>
            <div class="cell" data-sym="MCB"><div class="sym">MCB</div><div class="chg up" id="chg-MCB">+0.9%</div></div>
            <div class="cell" data-sym="MARI"><div class="sym">MARI</div><div class="chg up" id="chg-MARI">+3.1%</div></div>
            <div class="cell" data-sym="PPL"><div class="sym">PPL</div><div class="chg down" id="chg-PPL">-3.5%</div></div>
            <div class="cell" data-sym="BAHL"><div class="sym">BAHL</div><div class="chg up" id="chg-BAHL">+1.5%</div></div>
            <div class="cell" data-sym="SYS"><div class="sym">SYS</div><div class="chg up" id="chg-SYS">+2.6%</div></div>
            <div class="cell" data-sym="EFERT"><div class="sym">EFERT</div><div class="chg down" id="chg-EFERT">-4.2%</div></div>
            <div class="cell" data-sym="NBP"><div class="sym">NBP</div><div class="chg up" id="chg-NBP">+2.7%</div></div>
          </div>
          <div class="board-log" id="boardLog">
            <div id="logLine1">~/henneth-desk &gt; loading psx-universe<span class="l-caret" id="logCaret"></span></div>
            <div class="l-amber">advisory mode: disabled</div>
          </div>
        </div>

        <!-- research modules dock -->
        <div class="modules-dock" id="modulesDock">
          <div class="module" id="modValue" tabindex="0">
            <div class="m-head"><span>Value</span><span class="m-dot"></span></div>
            <div class="m-row"><span>Peer P/E</span><span>Earnings Power</span><span>Graham</span><span>Dividend Discount</span></div>
            <div class="m-explain">Four independent valuation models scored side by side — no single method decides the call.</div>
          </div>
          <div class="module" id="modDesk" tabindex="0">
            <div class="m-head"><span>Desk Room</span><span class="m-dot"></span></div>
            <div class="m-row"><span>Technical</span><span>Fundamental</span><span>Bull</span><span>Bear</span></div>
            <div class="m-explain">Four analyst roles debate every name before a view is published — bull and bear both stay visible.</div>
          </div>
          <div class="module" id="modGlobal" tabindex="0">
            <div class="m-head"><span>Global Tape</span><span class="m-dot"></span></div>
            <div class="m-row"><span>S&amp;P 500</span><span>VIX</span><span>Oil</span><span>Gold</span><span>EM</span></div>
            <div class="m-explain">PSX names are read against the global macro backdrop that moves them, not in isolation.</div>
          </div>
          <div class="module" id="modScore" tabindex="0">
            <div class="m-head"><span>Scorecard</span><span class="m-dot"></span></div>
            <div class="m-row"><span>Dated</span><span>Falsifiable</span><span>Scored</span><span>Misses Stay Visible</span></div>
            <div class="m-explain">Every call is timestamped and graded later — including the ones that were wrong.</div>
          </div>
        </div>

      </div>
    </div>

  </div>
</div>`;

  function unmount() {
    var prev = document.getElementById("hnAuthRoot");
    if (prev) prev.remove();
    document.body.classList.remove("hn-auth-open");
  }

  /* `tab` is 'signin' | 'create'. The starting tab is passed IN rather than switched after
     mount, because reconfigureTerminal() animates and would collide with the boot timeline. */
  function mount(tab) {
    unmount();
    var root = document.createElement("div");
    root.className = "hn-auth";
    root.id = "hnAuthRoot";
    root.innerHTML = HN_MARKUP;
    document.body.appendChild(root);
    document.body.classList.add("hn-auth-open");
    return hnAuthRun(root, tab);
  }

function hnAuthRun(root, initialTab){
  "use strict";

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasGSAP = typeof window.gsap !== 'undefined';

  /* Host integration seam. app.js replaces these after mount(); the terminal itself never
     talks to Supabase and never decides whether a credential is real. */
  var hooks = {
    onSubmit: null,        /* (tab) -> void. Set = the host owns the CTA. Unset = no-op. */
    onForgot: null,        /* (email) -> void. The password-reset link. */
    onTabChange: null,     /* (tab) -> void. Fired after the form repaints. */
    onOnboardingDone: null,/* (answers, how) -> void. how: 'confirmed' | 'blank' | 'skipped' | 'saved' */
    onEnterDesk: null      /* () -> void. The "Enter the desk" hand-off out of the terminal. */
  };

  var state = {
    tab: initialTab === 'create' ? 'create' : 'signin',
    onboardingStep: 0,
    onboardingAnswers: { goal: '', lens: '', horizon: '', radar: { sectors: [], tickers: [], source: '' } },
    onboarded: false
  };
  var tickers = [
    {sym:'FFC', val:2.9, up:true}, {sym:'UBL', val:-1.3, up:false}, {sym:'ENGROH', val:3.0, up:true},
    {sym:'MEBL', val:-1.5, up:false}, {sym:'HUBC', val:2.0, up:true}, {sym:'OGDC', val:3.8, up:true},
    {sym:'LUCK', val:-0.5, up:false}, {sym:'HBL', val:-1.7, up:false}, {sym:'MCB', val:0.9, up:true},
    {sym:'MARI', val:3.1, up:true}, {sym:'PPL', val:-3.5, up:false}, {sym:'BAHL', val:1.5, up:true},
    {sym:'SYS', val:2.6, up:true}, {sym:'EFERT', val:-4.2, up:false}, {sym:'NBP', val:2.7, up:true}
  ];

  var els = {
    formWrap: document.getElementById('formWrap'),
    headline: document.getElementById('headline'),
    subcopy: document.getElementById('subcopy'),
    tabSignin: document.getElementById('tabSignin'),
    tabCreate: document.getElementById('tabCreate'),
    nameField: document.getElementById('nameField'),
    nameInput: document.getElementById('nameInput'),
    emailInput: document.getElementById('emailInput'),
    pwInput: document.getElementById('pwInput'),
    pwToggle: document.getElementById('pwToggle'),
    errName: document.getElementById('errName'),
    errEmail: document.getElementById('errEmail'),
    errPw: document.getElementById('errPw'),
    forgotLine: document.getElementById('forgotLine'),
    authForgot: document.getElementById('authForgot'),
    capBox: document.getElementById('capBox'),
    authMsg: document.getElementById('authMsg'),
    meter: document.getElementById('meter'),
    meterCopy: document.getElementById('meterCopy'),
    m0: document.getElementById('m0'), m1: document.getElementById('m1'), m2: document.getElementById('m2'), m3: document.getElementById('m3'),
    ctaBtn: document.getElementById('ctaBtn'),
    ctaA: document.getElementById('ctaA'),
    ctaB: document.getElementById('ctaB'),
    switchPrompt: document.getElementById('switchPrompt'),
    switchLink: document.getElementById('switchLink'),
    rightPanel: document.getElementById('rightPanel'),
    parallaxLayer: document.getElementById('parallaxLayer'),
    descentScene: document.getElementById('descentScene'),
    descentAperture: document.getElementById('descentAperture'),
    descentFar: document.getElementById('descentFar'),
    descentMid: document.getElementById('descentMid'),
    descentForeground: document.getElementById('descentForeground'),
    conflictField: document.getElementById('conflictField'),
    descentLabel: document.getElementById('descentLabel'),
    depthReadout: document.getElementById('depthReadout'),
    calibrationOrbit: document.getElementById('calibrationOrbit'),
    universeSvg: document.getElementById('universeSvg'),
    universeGroup: document.getElementById('universeGroup'),
    evidenceLayer: document.getElementById('evidenceLayer'),
    statusLine: document.getElementById('statusLine'),
    statusPct: document.getElementById('statusPct'),
    pathFill: document.getElementById('pathFill'),
    seal: document.getElementById('seal'),
    sealRing: document.getElementById('sealRing'),
    sealTextPath: document.getElementById('sealTextPath'),
    board: document.getElementById('board'),
    tickerGrid: document.getElementById('tickerGrid'),
    modulesDock: document.getElementById('modulesDock'),
    modValue: document.getElementById('modValue'),
    modDesk: document.getElementById('modDesk'),
    modGlobal: document.getElementById('modGlobal'),
    modScore: document.getElementById('modScore'),
    boardLog: document.getElementById('boardLog'),
    logLine1: document.getElementById('logLine1'),
    onboardingShell: document.getElementById('onboardingShell'),
    onboardingKicker: document.getElementById('onboardingKicker'),
    onboardingTitle: document.getElementById('onboardingTitle'),
    onboardingProgress: document.getElementById('onboardingProgress'),
    onboardingTrackFill: document.getElementById('onboardingTrackFill'),
    onboardingCopy: document.getElementById('onboardingCopy'),
    onboardingStep: document.getElementById('onboardingStep'),
    onboardingActions: document.getElementById('onboardingActions'),
    onboardingBack: document.getElementById('onboardingBack'),
    onboardingNext: document.getElementById('onboardingNext'),
    onboardingSkip: document.getElementById('onboardingSkip'),
    onboardingSave: document.getElementById('onboardingSave'),
    todayShell: document.getElementById('todayShell'),
    todayTitle: document.getElementById('todayTitle'),
    todayBriefTitle: document.getElementById('todayBriefTitle'),
    todayBriefCopy: document.getElementById('todayBriefCopy'),
    todayRadarTitle: document.getElementById('todayRadarTitle'),
    todayRadarCopy: document.getElementById('todayRadarCopy'),
    todayNextTitle: document.getElementById('todayNextTitle'),
    todayNextCopy: document.getElementById('todayNextCopy'),
    todayLessonTitle: document.getElementById('todayLessonTitle'),
    todayLessonCopy: document.getElementById('todayLessonCopy'),
    checklist: document.getElementById('checklist'),
    enterDesk: document.getElementById('enterDesk'),
    todayResume: document.getElementById('todayResume')
  };

  var SEAL_TEXT = {
    signin: 'HENNETH DESK · PSX RESEARCH · RESEARCH NOT ADVICE · ',
    create: 'BULL CASE · BEAR CASE · VALUATION · RISK · '
  };

  /* Field errors and the status banner. The terminal renders them; the host decides what they
     say, so the validation copy stays in app.js next to the Supabase calls that produce it. */
  function setErr(which, msg){
    var el = els['err' + which.charAt(0).toUpperCase() + which.slice(1)];
    if (!el) return;
    el.textContent = msg || '';
    el.classList.toggle('on', !!msg);
  }
  function clearErrors(){ setErr('name',''); setErr('email',''); setErr('pw',''); }
  function setMsg(msg, isError){
    els.authMsg.textContent = msg || '';
    els.authMsg.hidden = !msg;
    els.authMsg.classList.toggle('bad', !!isError);
  }
  function setBusy(on){
    els.ctaBtn.disabled = !!on;
    els.ctaBtn.classList.toggle('busy', !!on);
  }

  function paintTab(tab, opts){
    opts = opts || {};
    var isCreate = tab === 'create';
    els.headline.textContent = isCreate ? 'Create Your Account' : 'Sign In To Henneth Desk';
    els.subcopy.textContent = 'Both sides of the argument, on every PSX stock.';
    els.tabSignin.setAttribute('aria-selected', String(!isCreate));
    els.tabCreate.setAttribute('aria-selected', String(isCreate));
    els.pwInput.placeholder = isCreate ? 'at least 10 characters' : 'your password';
    els.pwInput.setAttribute('autocomplete', isCreate ? 'new-password' : 'current-password');
    els.nameField.hidden = !isCreate;
    els.forgotLine.hidden = isCreate;
    clearErrors();
    els.ctaA.textContent = els.ctaB.textContent = isCreate ? 'Create Account' : 'Sign In';
    els.ctaBtn.style.marginTop = isCreate ? '4px' : '20px';
    els.switchPrompt.textContent = isCreate ? 'Already have an account?' : "Don't have an account yet?";
    els.switchLink.textContent = isCreate ? 'Sign In' : 'Create one';
    els.meter.classList.toggle('on', isCreate);
    els.meterCopy.classList.toggle('on', isCreate);
    if (!opts.silent) updateSealText(tab);
    if (hooks.onTabChange) hooks.onTabChange(tab);
  }

  function updateSealText(tab){
    if (els.sealTextPath) els.sealTextPath.textContent = SEAL_TEXT[tab] || SEAL_TEXT.signin;
  }

  function switchTab(){
    var next = state.tab === 'signin' ? 'create' : 'signin';
    reconfigureTerminal(next);
  }

  els.tabSignin.addEventListener('click', function(){ if(state.tab!=='signin') reconfigureTerminal('signin'); });
  els.tabCreate.addEventListener('click', function(){ if(state.tab!=='create') reconfigureTerminal('create'); });
  els.switchLink.addEventListener('click', switchTab);

  /* shortened terminal "reconfigure" replay on tab switch: board dims,
     modules shuffle, status line + seal text update, board resettles */
  function reconfigureTerminal(tab){
    state.tab = tab;
    var isCreate = tab === 'create';

    if (reduceMotion || !hasGSAP){
      paintTab(tab);
      els.statusLine.innerHTML = (isCreate ? 'Preparing new access' : 'Tracking the market&#8217;s path') + '<span class="caret"></span>';
      return;
    }

    var edges = els.universeGroup.querySelectorAll('.hn-edge');
    var cells = els.tickerGrid.querySelectorAll('.cell');
    var modules = els.modulesDock.querySelectorAll('.module');

    var tl = gsap.timeline();
    tl.to(edges, { opacity: 0.05, duration: 0.16, ease: 'power1.out' }, 0)
      .to(els.board, { filter: 'saturate(.5)', duration: 0.16 }, 0)
      .to(cells, { opacity: 0.25, y: 3, duration: 0.14, stagger: 0.006 }, 0)
      .to(modules, { opacity: 0.2, y: 4, duration: 0.14, stagger: 0.02 }, 0)
      .call(function(){
        paintTab(tab);
        els.statusLine.innerHTML = (isCreate ? 'Preparing new access' : 'Tracking the market&#8217;s path') + '<span class="caret"></span>';
      }, null, 0.18)
      .to(cells, { opacity: 1, y: 0, duration: 0.3, stagger: 0.015, ease: 'power2.out' }, 0.22)
      .to(modules, { opacity: 1, y: 0, duration: 0.28, stagger: 0.03, ease: 'power2.out' }, 0.24)
      .to(els.board, { filter: 'saturate(1)', duration: 0.3 }, 0.22)
      .to(edges, {
        opacity: function(i, target){
          if (target.classList.contains('hn-act1')) return 0.3;
          return target.getAttribute('data-syms') ? 0.34 : 0.16;
        },
        duration: 0.4, ease: 'power2.out', stagger: 0.003
      }, 0.3)
      .call(updateSealText, [tab], 0.5);
  }

  els.pwToggle.addEventListener('click', function(){
    var showing = els.pwInput.type === 'text';
    els.pwInput.type = showing ? 'password' : 'text';
    els.pwToggle.textContent = showing ? 'Show' : 'Hide';
  });

  els.pwInput.addEventListener('input', function(){
    var len = els.pwInput.value.length;
    var level = len === 0 ? 0 : len < 6 ? 1 : len < 10 ? 2 : len < 14 ? 3 : 4;
    [els.m0, els.m1, els.m2, els.m3].forEach(function(bar, i){
      bar.style.background = (level >= i+1) ? '#0a0a0a' : '#d9d9d2';
    });
  });

  /* The CTA only presses. Who is allowed in is the host's call (hooks.onSubmit), never the
     terminal's — the design file signed everyone in, the product must not. */
  els.ctaBtn.addEventListener('click', function(){
    els.ctaBtn.style.transform = 'scale(.985)';
    setTimeout(function(){ els.ctaBtn.style.transform = ''; }, 130);
    if (hooks.onSubmit) hooks.onSubmit(state.tab);
  });
  els.formWrap.addEventListener('keydown', function(ev){
    if (ev.key === 'Enter' && (ev.target === els.nameInput || ev.target === els.emailInput || ev.target === els.pwInput)){
      ev.preventDefault();
      els.ctaBtn.click();
    }
  });

  /* An error stops being true the moment the user edits the field it belongs to. */
  [['nameInput','name'], ['emailInput','email'], ['pwInput','pw']].forEach(function(pair){
    els[pair[0]].addEventListener('input', function(){ setErr(pair[1], ''); });
  });

  els.authForgot.addEventListener('click', function(){
    if (hooks.onForgot) hooks.onForgot(els.emailInput.value.trim());
  });

  /* ---------- personalized onboarding ---------- */
  var onboardingQuestions = [
    {
      key: 'goal',
      kicker: '01 / What matters first',
      title: 'What do you want the desk to help you do most?',
      copy: 'This sets the first thing you see when you arrive at Today.',
      options: [
        ['ideas', 'Find promising PSX ideas'], ['holdings', 'Monitor my existing holdings'],
        ['market', 'Understand the market each day'], ['strategy', 'Build a repeatable strategy'],
        ['learn', 'Learn investing properly'], ['chart', 'Explore the chart and Astro lens'],
        ['everything', 'A bit of everything']
      ]
    },
    {
      key: 'lens',
      kicker: '02 / Your decision lens',
      title: 'What is your main decision lens?',
      copy: 'We’ll change the order and language of Today, Screener, Strategies, Practice, and Astro.',
      options: [
        ['fundamentals', 'Fundamentals and valuation'], ['technicals', 'Technicals and momentum'],
        ['dividends', 'Dividends and income'], ['macro', 'Macro and sectors'],
        ['balanced', 'A balanced mix'], ['astro', 'Astro as an additional lens']
      ]
    },
    {
      key: 'horizon',
      kicker: '03 / Your pace',
      title: 'What is your time horizon?',
      copy: 'This tunes catalyst emphasis, lesson recommendations, and explanation depth.',
      options: [
        ['intraday', 'Intraday / very short-term'], ['weeks', 'Several days to a few weeks'],
        ['months', 'Several months'], ['longterm', 'Long-term compounding'],
        ['figuring', 'I am still figuring this out']
      ]
    }
  ];
  var onboardingLabels = {
    goal: { ideas:'Idea finder', holdings:'Portfolio monitor', market:'Market reader', strategy:'Strategy builder', learn:'Learner', chart:'Chart / Astro explorer', everything:'Balanced researcher' },
    lens: { fundamentals:'Fundamentals-first', technicals:'Technicals-led', dividends:'Income-aware', macro:'Macro-aware', balanced:'Balanced', astro:'Astro-aware' },
    horizon: { intraday:'Very short-term', weeks:'Short swing', months:'Several months', longterm:'Long-term', figuring:'Still exploring' }
  };

  /* One lesson per decision lens, so "Your next lesson" is genuinely tied to what the user
     answered. The preview card and Today read the same map — the desk must not promise one
     lesson in the preview and open a different one. */
  var onboardingLessons = {
    fundamentals: ['The balance sheet, line by line', 'Read one PSX balance sheet end to end and know what the numbers are telling you.'],
    technicals:   ['Support, resistance, and what a break really means', 'Mark the levels on one PSX chart, then watch what price does at each of them.'],
    dividends:    ['Yield, payout ratio, and book closure', 'How a PSX dividend is actually paid — and what a very high yield is often hiding.'],
    macro:        ['Rates, the rupee, and who feels them first', 'Trace one SBP decision through to the PSX sectors it moves.'],
    astro:        ['Reading the astro lens without fooling yourself', 'What the desk tests, what it scores, and what it refuses to claim.'],
    balanced:     ['How the desk builds a case', 'Bull case, bear case, valuation, risk — the four parts of every read on this desk.']
  };
  function lessonFor(a){ return onboardingLessons[a.lens] || onboardingLessons.balanced; }

  function persistOnboarding(){
    try{ localStorage.setItem('henneth-onboarding-draft', JSON.stringify({ answers: state.onboardingAnswers, step: state.onboardingStep })); }catch(err){}
  }

  var goalModules = {
    ideas: ['modDesk','modValue','modScore','modGlobal'],
    holdings: ['modScore','modGlobal','modValue','modDesk'],
    market: ['modGlobal','modDesk','modScore','modValue'],
    strategy: ['modDesk','modScore','modValue','modGlobal'],
    learn: ['modDesk','modValue','modScore','modGlobal'],
    chart: ['modDesk','modGlobal','modValue','modScore'],
    everything: ['modDesk','modGlobal','modValue','modScore']
  };
  var goalStatus = {
    ideas: 'Preparing an idea-finding desk', holdings: 'Preparing a portfolio-monitoring desk',
    market: 'Preparing a market-reading desk', strategy: 'Preparing a strategy desk',
    learn: 'Preparing a learning path', chart: 'Preparing a chart and Astro desk', everything: 'Preparing a balanced desk'
  };
  var lensStatus = {
    fundamentals: 'Routing the desk through valuation', technicals: 'Routing the desk through momentum',
    dividends: 'Routing the desk through income', macro: 'Connecting the global tape to PSX',
    balanced: 'Balancing technical and fundamental evidence', astro: 'Adding Astro as an optional lens'
  };
  var sectorSymbols = {
    Banks: ['HBL','MCB','BAHL','NBP'], 'E&P': ['OGDC','PPL','MARI'], Cement: ['LUCK','HUBC'],
    Technology: ['SYS'], Fertilizers: ['FFC','ENGROH','EFERT'], OMCs: ['PSO','SHEL']
  };
  var goalEvidence = {
    ideas: ['value','momentum','earnings'], holdings: ['risk','dividend','earnings'], market: ['macro','earnings','risk'],
    strategy: ['value','momentum','risk'], learn: ['value','risk'], chart: ['momentum','macro'], everything: ['value','momentum','dividend','macro','risk','earnings']
  };

  function setTerminalStatus(line, pct){
    if (!els.statusLine) return;
    pct = pct == null ? 100 : pct;
    els.statusLine.innerHTML = line + '<span class="caret"></span>';
    els.statusPct.textContent = pct + '%';
    els.statusPct.setAttribute('aria-valuenow', String(pct));
    if (hasGSAP && !reduceMotion){ gsap.to(els.pathFill, {width:pct + '%', duration:.55, ease:'power2.out'}); }
    else { els.pathFill.style.width = pct + '%'; }
    els.rightPanel.classList.add('onboarding-right');
    els.logLine1.innerHTML = '~/henneth-desk &gt; ' + line.toLowerCase();
  }

  function animateCalibration(){
    els.rightPanel.classList.add('calibrating');
    if (reduceMotion || !hasGSAP){
      els.board.style.transform = 'none';
      els.calibrationOrbit.style.opacity = '.42';
      return;
    }
    gsap.killTweensOf([els.board, els.universeGroup, els.calibrationOrbit]);
    gsap.timeline({defaults:{ease:'power2.out'}})
      .to(els.universeGroup,{scale:1.012,duration:.42},0)
      .to(els.calibrationOrbit,{scale:1.04,duration:.28},0)
      .to(els.board,{y:-3,duration:.18},.12)
      .to(els.board,{y:0,duration:.28,ease:'power2.inOut'},.3)
      .to(els.calibrationOrbit,{scale:1,duration:.3},.3);
  }

  var descentTimeline = null;
  var descentDepth = { threshold:'DEPTH 00 · SURFACE', goal:'DEPTH 01 · BREACH', lens:'DEPTH 02 · EVIDENCE STRATA', horizon:'DEPTH 03 · CHAMBER OF DOUBT', radar:'DEPTH 04 · RETRIEVAL', final:'DEPTH 00 · CALIBRATED' };
  var descentLabels = { threshold:'SURFACE MAP INCOMPLETE', goal:'OPENING THE EVIDENCE LAYER', lens:'FOLLOWING YOUR CHOSEN SIGNAL', horizon:'THE MARKET IS NOT RESOLVING CLEANLY', radar:'RECOVERING YOUR RADAR', final:'RETURNING WITH A CALIBRATED VIEW' };
  var goalDescentStatus = { ideas:'Opening the idea-finding path', holdings:'Entering the holdings layer', market:'Following the market signal', strategy:'Opening the strategy archive', learn:'Entering the learning path', chart:'Following the chart signal', everything:'Opening the balanced path' };

  function killDescentTimeline(){
    if (descentTimeline){ descentTimeline.kill(); descentTimeline = null; }
    if (hasGSAP){ gsap.killTweensOf([els.universeSvg,els.universeGroup,els.board,els.descentAperture,els.descentFar,els.descentMid,els.descentForeground,els.conflictField]); }
  }
  function setDepthReadout(key){ if (els.depthReadout) els.depthReadout.textContent = descentDepth[key] || descentDepth.threshold; }
  function setDescentLabel(key){ if (els.descentLabel) els.descentLabel.textContent = descentLabels[key] || key.toUpperCase(); }
  function resetDescentClasses(){
    ['descent-on','descent-surface','descent-threshold','descent-breach','descent-lens-active','descent-conflict','descent-retrieval','descent-final','descent-fast','descent-wide','descent-orbit','descent-lens-fundamentals','descent-lens-technicals','descent-lens-dividends','descent-lens-macro','descent-lens-balanced','descent-lens-astro'].forEach(function(name){ els.rightPanel.classList.remove(name); });
  }
  function enterThreshold(){
    killDescentTimeline();
    els.rightPanel.classList.add('descent-on','descent-surface','descent-threshold');
    setDepthReadout('threshold'); setDescentLabel('threshold');
    els.statusLine.innerHTML = 'Surface map incomplete<span class="caret"></span>';
    if (els.sealRing) els.sealRing.style.animationPlayState = 'paused';
    if (reduceMotion || !hasGSAP){ els.descentAperture.style.opacity='.6'; els.descentAperture.style.transform='translate(-50%,-50%) scale(.82)'; return; }
    descentTimeline = gsap.timeline({defaults:{ease:'power2.out'}})
      .to(els.descentAperture,{opacity:.55,scale:.82,duration:.8},0)
      .to(els.descentFar,{opacity:.24,z:-80,duration:.75},.1)
      .to(els.board,{x:-18,y:5,duration:.7},.15)
      .call(function(){ els.statusLine.innerHTML='A deeper path is available<span class="caret"></span>'; },null,.72);
  }
  function runDescentChapter(type, value){
    killDescentTimeline();
    els.rightPanel.classList.add('descent-on');
    els.rightPanel.classList.remove('descent-surface','descent-threshold','descent-final');
    ['descent-breach','descent-lens-active','descent-conflict','descent-retrieval','descent-fast','descent-wide','descent-lens-fundamentals','descent-lens-technicals','descent-lens-dividends','descent-lens-macro','descent-lens-balanced','descent-lens-astro'].forEach(function(name){ els.rightPanel.classList.remove(name); });
    setDepthReadout(type); setDescentLabel(type);
    if (type === 'goal'){
      els.rightPanel.classList.add('descent-breach');
      setTerminalStatus(goalDescentStatus[value] || goalDescentStatus.everything, 18);
      if (reduceMotion || !hasGSAP){ els.universeSvg.style.transform='scale(1.32)'; els.descentAperture.style.opacity='.9'; els.board.style.opacity='.16'; return; }
      descentTimeline = gsap.timeline({defaults:{ease:'power3.inOut'}})
        .to(els.universeSvg,{scale:1.28,x:-44,y:-18,duration:1.05},0)
        .to(els.descentAperture,{opacity:.9,scale:1.35,duration:1.0},0)
        .to(els.board,{x:-120,y:42,scale:.78,opacity:.14,duration:.85,ease:'power2.in'},.05)
        .to(els.descentMid,{opacity:.56,z:90,scale:1.08,duration:.82},.2)
        .to(els.descentForeground,{opacity:.32,z:150,scale:1.12,duration:.9},.35)
        .call(function(){ els.statusLine.innerHTML='Opening the evidence layer<span class="caret"></span>'; },null,.72);
    } else if (type === 'lens'){
      els.rightPanel.classList.add('descent-breach','descent-lens-active','descent-lens-' + value);
      setTerminalStatus('Following your chosen signal', 42);
      if (reduceMotion || !hasGSAP){ routeGraph(value); els.conflictField.style.opacity='.76'; return; }
      descentTimeline = gsap.timeline({defaults:{ease:'power2.inOut'}})
        .to(els.universeSvg,{scale:value==='macro'?1.62:1.5,x:value==='macro'?-90:-58,y:value==='macro'?-28:-34,duration:1.1},0)
        .to(els.descentFar,{opacity:value==='macro'?.62:.28,z:-160,scale:value==='macro'?1.18:.94,duration:.8},0)
        .to(els.descentMid,{opacity:value==='dividends'?.74:.56,z:110,rotationY:value==='astro'?-10:0,duration:.9},.08)
        .to(els.descentForeground,{opacity:.72,z:210,scale:1.22,duration:.95},.18)
        .to(els.conflictField,{opacity:value==='balanced'?.78:.22,scale:1,duration:.55},.42)
        .call(function(){ routeGraph(value); els.statusLine.innerHTML=(lensStatus[value] || 'Opening the evidence layer')+'<span class="caret"></span>'; },null,.7);
    } else if (type === 'horizon'){
      var fast = value === 'intraday' || value === 'weeks';
      els.rightPanel.classList.add('descent-conflict');
      if (fast) els.rightPanel.classList.add('descent-fast');
      if (value === 'months' || value === 'longterm') els.rightPanel.classList.add('descent-wide');
      setTerminalStatus(fast ? 'Short-term signal conflict' : value === 'longterm' ? 'Longer evidence horizon selected' : 'The market is not resolving cleanly', 58);
      if (reduceMotion || !hasGSAP){ els.conflictField.style.opacity='.86'; return; }
      descentTimeline = gsap.timeline({defaults:{ease:'power2.inOut'}})
        .to(els.universeSvg,{scale:value==='longterm'?.92:value==='months'?1.18:1.68,x:value==='longterm'?22:-38,y:value==='longterm'?18:-40,duration:1.2},0)
        .to(els.conflictField,{opacity:.88,scale:1.02,duration:.5},.34)
        .to(els.descentForeground,{opacity:value==='longterm'?.22:.62,z:value==='longterm'?80:230,duration:.8},.18)
        .to(els.descentMid,{opacity:value==='longterm'?.42:.72,duration:.7},.28)
        .to({}, {duration:.48},.72)
        .call(function(){ els.statusLine.innerHTML='Both sides remain visible<span class="caret"></span>'; },null,1.05);
    } else if (type === 'radar'){
      els.rightPanel.classList.add('descent-breach','descent-retrieval');
      setTerminalStatus('Recovering your radar', 74);
      syncRadarBoard();
      if (reduceMotion || !hasGSAP){ retrieveRadarSymbols(); return; }
      descentTimeline = gsap.timeline({defaults:{ease:'power2.out'}})
        .to(els.universeSvg,{scale:1.72,x:-66,y:-42,duration:.9},0)
        .to(els.descentAperture,{opacity:.98,scale:1.85,duration:.8},0)
        .to(els.board,{x:0,y:0,scale:1,opacity:1,duration:.95,ease:'power3.out'},.12)
        .call(function(){ retrieveRadarSymbols(); },null,.45)
        .call(function(){ els.statusLine.innerHTML='Radar node secured<span class="caret"></span>'; },null,1.15);
    }
  }

  function retrieveRadarSymbols(){
    var symbols = radarSymbols();
    if (!symbols.length){ setTerminalStatus('Current market read recovered', 76); return; }
    if (reduceMotion || !hasGSAP){
      symbols.forEach(function(sym){ var cell=els.tickerGrid.querySelector('.cell[data-sym="' + sym + '"]'); if(cell){ cell.classList.add('radar-selected'); cell.classList.remove('radar-muted'); } });
      setTerminalStatus('Radar node secured', 76);
      return;
    }
    var panelRect = els.rightPanel.getBoundingClientRect();
    symbols.forEach(function(sym,index){
      var node = document.getElementById('node-' + sym);
      var cell = els.tickerGrid.querySelector('.cell[data-sym="' + sym + '"]');
      if (!cell) return;
      var nodeRect = node ? node.getBoundingClientRect() : {left:panelRect.left + panelRect.width*.5, top:panelRect.top + panelRect.height*.46, width:1, height:1};
      var cellRect = cell.getBoundingClientRect();
      var specimen = document.createElement('div');
      specimen.className='recovery-specimen'; specimen.setAttribute('data-od-id','recovery-' + sym.toLowerCase()); specimen.textContent=sym;
      specimen.style.left=(nodeRect.left-panelRect.left+nodeRect.width/2-38)+'px'; specimen.style.top=(nodeRect.top-panelRect.top+nodeRect.height/2-14)+'px';
      els.rightPanel.appendChild(specimen);
      if (node) node.classList.add('hn-hot');
      gsap.fromTo(specimen,{scale:.65,opacity:0},{scale:1,opacity:1,duration:.2,delay:index*.18,ease:'power2.out'});
      gsap.to(specimen,{left:(cellRect.left-panelRect.left+cellRect.width/2-38)+'px',top:(cellRect.top-panelRect.top+cellRect.height/2-14)+'px',duration:.84,delay:index*.18,ease:'power3.inOut',onComplete:function(){ cell.classList.add('radar-selected'); cell.classList.remove('radar-muted'); specimen.remove(); if(index===symbols.length-1){ els.logLine1.innerHTML='~/henneth-desk &gt; evidence recovered · radar indexed'; } }});
    });
  }

  function returnToSurface(done){
    killDescentTimeline();
    ['descent-threshold','descent-breach','descent-lens-active','descent-conflict','descent-retrieval','descent-fast','descent-wide'].forEach(function(name){ els.rightPanel.classList.remove(name); });
    els.rightPanel.classList.add('descent-final');
    setDepthReadout('final'); setDescentLabel('final'); setTerminalStatus('Returning with a calibrated view', 92);
    if (reduceMotion || !hasGSAP){ els.universeSvg.style.transform='none'; els.board.style.transform='none'; els.descentAperture.style.opacity='.22'; if(els.sealRing) els.sealRing.style.animationPlayState='running'; if(done) done(); return; }
    descentTimeline = gsap.timeline({defaults:{ease:'power3.inOut'},onComplete:function(){ if(done) done(); }})
      .to(els.universeSvg,{scale:1,x:0,y:0,duration:1.35},0)
      .to(els.descentAperture,{opacity:.22,scale:.74,duration:1.15},0)
      .to(els.descentFar,{opacity:.18,z:0,scale:1,duration:1.1},.08)
      .to(els.descentMid,{opacity:.22,z:0,scale:1,duration:1.05},.14)
      .to(els.descentForeground,{opacity:.34,z:0,scale:1,duration:1.05},.18)
      .to(els.conflictField,{opacity:.22,scale:.78,duration:.72},.32)
      .to(els.board,{x:0,y:0,scale:1,opacity:1,duration:1.2},.14)
      .call(function(){ if(els.sealRing) els.sealRing.style.animationPlayState='running'; els.statusLine.innerHTML='Your desk is prepared<span class="caret"></span>'; els.logLine1.innerHTML='~/henneth-desk &gt; evidence recovered · radar indexed · lens calibrated'; },null,1.05);
  }

  function focusEvidence(keys){
    var keySet = keys || [];
    els.evidenceLayer.querySelectorAll('.ev-onboarding').forEach(function(frag){
      var active = keySet.indexOf(frag.getAttribute('data-evidence')) !== -1;
      frag.classList.toggle('ev-focus', active);
      frag.classList.toggle('ev-dim', !active);
    });
    animateCalibration();
  }

  function routeGraph(lens){
    ['fundamentals','technicals','dividends','macro','balanced','astro'].forEach(function(name){ els.rightPanel.classList.remove('lens-' + name); });
    els.rightPanel.classList.add('lens-' + lens);
    var edges = els.universeGroup.querySelectorAll('.hn-edge:not(.hn-act1)');
    var emphasis = lens === 'balanced' ? null : (lens === 'fundamentals' ? ['FFC','ENGROH','EFERT','BAHL','MEBL'] : lens === 'technicals' ? ['MEBL','SYS','LUCK','HBL'] : lens === 'dividends' ? ['FFC','ENGROH','EFERT','HUBC'] : lens === 'macro' ? ['MARI','OGDC','PPL','HUBC'] : lens === 'astro' ? ['MARI','SYS','BAHL'] : []);
    if (reduceMotion || !hasGSAP){
      edges.forEach(function(edge){ var syms=(edge.getAttribute('data-syms')||''); edge.style.opacity = !emphasis || emphasis.some(function(s){return syms.indexOf(s)!==-1;}) ? '.62' : '.1'; });
    } else {
      gsap.killTweensOf(edges);
      gsap.to(edges,{opacity:.1,duration:.22,stagger:.004,overwrite:true});
      if (!emphasis){ gsap.to(edges,{opacity:.42,duration:.45,stagger:.006,overwrite:true}); }
      else { gsap.to(Array.prototype.filter.call(edges,function(edge){ var syms=edge.getAttribute('data-syms')||''; return emphasis.some(function(s){return syms.indexOf(s)!==-1;}); }),{opacity:.72,duration:.55,stagger:.012,overwrite:true}); }
    }
    if (lens === 'astro') els.calibrationOrbit.style.opacity = '.68';
  }

  function reorderModules(goal){
    var order = goalModules[goal] || goalModules.everything;
    order.forEach(function(id, index){ var mod=document.getElementById(id); if(mod){ mod.style.order=String(index); mod.classList.toggle('priority', index < 2); } });
    if (hasGSAP && !reduceMotion){
      var mods = els.modulesDock.querySelectorAll('.module');
      gsap.fromTo(mods,{y:5},{y:0,duration:.35,stagger:.04,overwrite:true,ease:'power2.out'});
    }
  }

  function radarSymbols(){
    var radar = state.onboardingAnswers.radar || {sectors:[],tickers:[]};
    var result = [];
    (radar.sectors || []).forEach(function(sector){ (sectorSymbols[sector] || []).forEach(function(sym){ if(result.indexOf(sym)===-1) result.push(sym); }); });
    (radar.tickers || []).forEach(function(sym){ if(result.indexOf(sym)===-1) result.push(sym); });
    return result.slice(0,8);
  }

  function syncRadarBoard(){
    var symbols = radarSymbols();
    var existing = {};
    els.tickerGrid.querySelectorAll('.cell').forEach(function(cell){ existing[cell.getAttribute('data-sym')] = cell; cell.classList.remove('radar-selected','radar-muted'); });
    symbols.forEach(function(sym){
      if (!existing[sym]){
        var cell=document.createElement('div'); cell.className='cell radar-selected'; cell.setAttribute('data-sym',sym); cell.setAttribute('data-od-id','radar-cell-' + sym.toLowerCase()); cell.setAttribute('tabindex','0'); cell.innerHTML='<div class="sym">'+sym+'</div><div class="chg">—</div>'; els.tickerGrid.appendChild(cell); existing[sym]=cell;
      }
      existing[sym].classList.add('radar-selected');
    });
    if (symbols.length){ els.tickerGrid.querySelectorAll('.cell').forEach(function(cell){ if(symbols.indexOf(cell.getAttribute('data-sym'))===-1) cell.classList.add('radar-muted'); }); }
    els.universeGroup.querySelectorAll('.hn-edge').forEach(function(edge){ var syms=(edge.getAttribute('data-syms')||'').split(','); var hit=symbols.some(function(sym){return syms.indexOf(sym)!==-1;}); edge.classList.toggle('hn-hot',hit); edge.classList.toggle('hn-dim',symbols.length>0 && !hit); });
    els.universeGroup.querySelectorAll('.hn-node,.hn-label').forEach(function(node){ var sym=node.getAttribute('data-sym'); var hit=symbols.indexOf(sym)!==-1; node.classList.toggle('hn-hot',hit); node.classList.toggle('hn-dim',symbols.length>0 && !hit); });
    if (hasGSAP && !reduceMotion){
      var selected = els.tickerGrid.querySelectorAll('.radar-selected');
      gsap.fromTo(selected,{opacity:0,y:6},{opacity:1,y:0,duration:.35,stagger:.06,overwrite:true,ease:'power2.out'});
    }
    animateCalibration();
  }

  function applyOnboardingSignal(type, value){
    if (type === 'goal'){
      focusEvidence(goalEvidence[value] || goalEvidence.everything);
      reorderModules(value);
      runDescentChapter('goal', value);
    } else if (type === 'lens'){
      routeGraph(value);
      runDescentChapter('lens', value);
    } else if (type === 'horizon'){
      runDescentChapter('horizon', value);
    } else if (type === 'radar'){
      runDescentChapter('radar', value);
    }
  }

  function onboardingProgress(step){
    var current = Math.min(step + 1, 4);
    els.onboardingProgress.innerHTML = '<strong>' + current + ' / 4</strong>' + (step >= 4 ? 'Desk ready' : 'Calibrating your desk');
    els.onboardingTrackFill.style.width = (step >= 4 ? 100 : current * 25) + '%';
  }

  function renderOnboardingStep(){
    var step = state.onboardingStep;
    onboardingProgress(step);
    if (els.onboardingBack) els.onboardingBack.hidden = step === 0;
    if (step < 3){
      var q = onboardingQuestions[step];
      els.onboardingKicker.textContent = q.kicker;
      els.onboardingTitle.textContent = q.title;
      els.onboardingCopy.textContent = q.copy;
      els.onboardingStep.innerHTML = '<div class="choice-list" data-od-id="choice-list">' + q.options.map(function(opt){
        var selected = state.onboardingAnswers[q.key] === opt[0];
        return '<button type="button" class="choice" data-choice="' + opt[0] + '" aria-pressed="' + selected + '" data-od-id="choice-' + opt[0] + '">' + opt[1] + '</button>';
      }).join('') + '</div>';
      els.onboardingNext.textContent = step === 0 ? 'Open path' : step === 1 ? 'Descend through lens' : 'Enter the radar';
      els.onboardingNext.disabled = !state.onboardingAnswers[q.key];
      els.onboardingStep.querySelectorAll('.choice').forEach(function(btn){
        btn.addEventListener('click', function(){
          state.onboardingAnswers[q.key] = btn.getAttribute('data-choice');
          els.onboardingStep.querySelectorAll('.choice').forEach(function(other){ other.setAttribute('aria-pressed', String(other === btn)); });
          els.onboardingNext.disabled = false;
          applyOnboardingSignal(q.key, state.onboardingAnswers[q.key]);
          persistOnboarding();
        });
      });
      return;
    }

    els.onboardingKicker.textContent = '04 / Put something on the radar';
    els.onboardingTitle.textContent = 'What should we put on your radar first?';
    els.onboardingCopy.textContent = 'Pick a few sectors, add 3–5 tickers, import holdings, or start with the desk’s current market read.';
    var sectors = ['Banks','E&P','Cement','Technology','Fertilizers','OMCs'];
    var selectedSectors = state.onboardingAnswers.radar.sectors;
    els.onboardingStep.innerHTML = '<div class="radar-grid">' +
      '<div><span class="radar-label">Sectors</span><div class="sector-list">' + sectors.map(function(s){ var active=selectedSectors.indexOf(s)!==-1; return '<button type="button" class="sector" data-sector="' + s + '" aria-pressed="' + active + '" data-od-id="sector-' + s.toLowerCase().replace(/[^a-z]+/g,'-') + '">' + s + '</button>'; }).join('') + '</div></div>' +
      '<div><span class="radar-label">Tickers</span><div class="radar-row"><input class="radar-input" id="radarTickerInput" maxlength="8" placeholder="e.g. MEBL" aria-label="Add ticker" /><button type="button" class="ticker-add" id="tickerAdd" data-od-id="ticker-add">Add</button></div><div class="ticker-chips" id="tickerChips"></div></div>' +
      '<div><span class="radar-label">Or start with</span><div class="choice-list"><button type="button" class="choice" data-source="holdings" aria-pressed="' + (state.onboardingAnswers.radar.source === 'holdings') + '">My holdings</button><button type="button" class="choice" data-source="market-read" aria-pressed="' + (state.onboardingAnswers.radar.source === 'market-read') + '">Current market read</button></div><p class="radar-note">Nothing is overwritten. You can refine this from Today.</p></div>' +
      '</div>';
    els.onboardingNext.textContent = 'Recover my radar';
    els.onboardingNext.disabled = !(selectedSectors.length || state.onboardingAnswers.radar.tickers.length || state.onboardingAnswers.radar.source);

    function paintTickerChips(){
      var chips = els.onboardingStep.querySelector('#tickerChips');
      chips.innerHTML = state.onboardingAnswers.radar.tickers.map(function(t){ return '<span class="ticker-chip">' + t + '<button type="button" data-remove-ticker="' + t + '" aria-label="Remove ' + t + '">×</button></span>'; }).join('');
      chips.querySelectorAll('[data-remove-ticker]').forEach(function(btn){ btn.addEventListener('click', function(){ state.onboardingAnswers.radar.tickers = state.onboardingAnswers.radar.tickers.filter(function(t){ return t !== btn.getAttribute('data-remove-ticker'); }); paintTickerChips(); updateRadarNext(); persistOnboarding(); }); });
    }
    function updateRadarNext(){ els.onboardingNext.disabled = !(selectedSectors.length || state.onboardingAnswers.radar.tickers.length || state.onboardingAnswers.radar.source); }
    paintTickerChips();
    els.onboardingStep.querySelectorAll('[data-sector]').forEach(function(btn){ btn.addEventListener('click', function(){ var s=btn.getAttribute('data-sector'); var idx=selectedSectors.indexOf(s); if(idx===-1){ selectedSectors.push(s); } else { selectedSectors.splice(idx,1); } btn.setAttribute('aria-pressed', String(idx===-1)); updateRadarNext(); applyOnboardingSignal('radar', s); persistOnboarding(); }); });
    els.onboardingStep.querySelectorAll('[data-source]').forEach(function(btn){ btn.addEventListener('click', function(){ state.onboardingAnswers.radar.source = btn.getAttribute('data-source'); els.onboardingStep.querySelectorAll('[data-source]').forEach(function(other){ other.setAttribute('aria-pressed', String(other === btn)); }); updateRadarNext(); applyOnboardingSignal('radar', state.onboardingAnswers.radar.source); persistOnboarding(); }); });
    els.onboardingStep.querySelector('#tickerAdd').addEventListener('click', function(){ var input=els.onboardingStep.querySelector('#radarTickerInput'); var val=(input.value||'').trim().toUpperCase().replace(/[^A-Z0-9.]/g,''); if(!val || state.onboardingAnswers.radar.tickers.indexOf(val)!==-1 || state.onboardingAnswers.radar.tickers.length>=5) return; state.onboardingAnswers.radar.tickers.push(val); input.value=''; paintTickerChips(); updateRadarNext(); applyOnboardingSignal('radar', val); persistOnboarding(); });
  }

  function startOnboarding(){
    if (state.onboarded) return;
    try{
      if(localStorage.getItem('henneth-onboarding-skipped') === '1'){ state.onboarded=true; showToday(); return; }
      var saved = JSON.parse(localStorage.getItem('henneth-onboarding-draft') || 'null');
      if(saved && saved.answers) { state.onboardingAnswers = saved.answers; state.onboardingStep = Math.min(3, Number(saved.step) || 0); }
      else if(saved && saved.goal !== undefined) state.onboardingAnswers = saved;
    }catch(err){}
    els.formWrap.style.display = 'none';
    els.onboardingShell.hidden = false;
    els.todayShell.hidden = true;
    els.rightPanel.classList.add('calibrating');
    renderOnboardingStep();
    setTerminalStatus('Listening for your research path', 0);
    enterThreshold();
    if (hasGSAP){ gsap.fromTo(els.onboardingShell, {opacity:0,y:10}, {opacity:1,y:0,duration:.35,ease:'power2.out'}); }
    else { els.onboardingShell.style.opacity = 1; els.onboardingShell.style.transform = 'none'; }
  }

  function prepareDesk(){
    routeGraph(state.onboardingAnswers.lens || 'balanced');
    reorderModules(state.onboardingAnswers.goal || 'everything');
    syncRadarBoard();
    els.onboardingKicker.textContent = 'Setup in progress';
    els.onboardingTitle.textContent = 'Preparing your desk for you';
    els.onboardingCopy.textContent = 'Each change below is tied to what you just told us. Nothing touches existing lists or chart data.';
    els.onboardingTrackFill.style.width = '100%';
    els.onboardingStep.innerHTML = '<div class="setup-state"><div class="setup-list"><div class="setup-item"><span class="setup-mark">✓</span> Setting your daily brief to ' + (onboardingLabels.lens[state.onboardingAnswers.lens] || 'balanced') + ' explanations</div><div class="setup-item"><span class="setup-mark">✓</span> Prioritizing ' + (state.onboardingAnswers.radar.sectors.join(' and ') || 'your current radar') + ' and relevant catalysts</div><div class="setup-item"><span class="setup-mark">✓</span> Loading a ' + (onboardingLabels.lens[state.onboardingAnswers.lens] || 'balanced') + ' screener</div><div class="setup-item"><span class="setup-mark">✓</span> Choosing your first 8-minute lesson</div><div class="setup-item"><span class="setup-mark">✓</span> Building your starting radar</div></div></div>';
    els.onboardingActions.innerHTML = '';
    setTerminalStatus('Indexing your radar', 75);
    var items = els.onboardingStep.querySelectorAll('.setup-item');
    items.forEach(function(item, i){ item.style.opacity = 0; item.style.transform = 'translateY(5px)'; setTimeout(function(){ item.style.opacity = 1; item.style.transform = 'none'; item.style.transition = 'opacity .25s ease, transform .25s ease'; }, 130 + i * 220); });
    setTimeout(renderPreview, 1450);
  }

  function renderPreview(){
    syncRadarBoard();
    els.onboardingKicker.textContent = 'Ready to confirm';
    els.onboardingTitle.textContent = 'Your desk is ready';
    els.onboardingCopy.textContent = 'Here’s the shape we’ll use for Today. You can edit this setup whenever you want.';
    els.onboardingStep.innerHTML = '<div class="preview-card" data-od-id="onboarding-preview"><div class="preview-head"><strong>' + (onboardingLabels.lens[state.onboardingAnswers.lens] || 'Balanced') + ', ' + (onboardingLabels.horizon[state.onboardingAnswers.horizon] || 'PSX researcher') + '</strong><span>Preview</span></div><div class="preview-body"><div><p><strong>Today:</strong> Macro context first, then quality names and catalysts.</p><p><strong>Radar:</strong> ' + (state.onboardingAnswers.radar.sectors.concat(state.onboardingAnswers.radar.tickers).join(', ') || 'The desk’s current market read') + '</p></div><div><p><strong>Next lesson:</strong> ' + lessonFor(state.onboardingAnswers)[0] + '.</p><p><strong>Starting action:</strong> Review today’s brief and save one name.</p></div></div></div>';
    els.onboardingActions.innerHTML = '<div class="onboarding-links"><button type="button" class="onboarding-link" id="editSetup">Edit my setup</button><button type="button" class="onboarding-link" id="blankDesk">Start with a blank desk</button></div><button type="button" class="onboarding-action primary" id="looksRight">Looks right</button>';
    els.onboardingActions.querySelector('#looksRight').addEventListener('click', function(){ state.onboarded=true; localStorage.removeItem('henneth-onboarding-draft'); finishOnboarding('confirmed'); returnToSurface(showToday); });
    els.onboardingActions.querySelector('#editSetup').addEventListener('click', function(){ els.onboardingActions.innerHTML = '<div class="onboarding-links"><button type="button" class="onboarding-link" id="onboardingSkip" data-od-id="onboarding-skip">Skip for now</button><button type="button" class="onboarding-link" id="onboardingSave" data-od-id="onboarding-save">Save and continue later</button><button type="button" class="onboarding-link" id="onboardingKnow" data-od-id="onboarding-know">I already know what I want</button></div><button type="button" class="onboarding-action ghost" id="onboardingBack" data-od-id="onboarding-back" hidden>Back</button><button type="button" class="onboarding-action primary" id="onboardingNext" data-od-id="onboarding-next">Open path</button>'; wireOnboardingActions(); state.onboardingStep=0; renderOnboardingStep(); });
    els.onboardingActions.querySelector('#blankDesk').addEventListener('click', function(){ state.onboardingAnswers = { goal:'everything', lens:'balanced', horizon:'figuring', radar:{sectors:[],tickers:[],source:'market-read'} }; state.onboarded=true; finishOnboarding('blank'); returnToSurface(showToday); });
    setTerminalStatus('Desk preview ready', 75);
  }

  /* One exit for every way onboarding can end, so the host persists exactly once and knows
     WHICH ending it was — a blank desk must not look like a confirmed profile. */
  function finishOnboarding(how){
    if (hooks.onOnboardingDone) hooks.onOnboardingDone(state.onboardingAnswers, how);
  }

  function showToday(){
    els.onboardingShell.hidden = true;
    els.todayShell.hidden = false;
    var a=state.onboardingAnswers;
    var label=onboardingLabels.goal[a.goal] || 'Balanced researcher';
    els.todayTitle.textContent = 'Good morning. We prepared today’s desk for you.';
    els.todayBriefTitle.textContent = (onboardingLabels.lens[a.lens] || 'Balanced') + ' context, then the names worth a closer look.';
    els.todayBriefCopy.textContent = 'Your ' + label.toLowerCase() + ' path starts with a clear market read, then one action you can finish in a few minutes.';
    els.todayRadarTitle.textContent = a.radar.sectors.concat(a.radar.tickers).join(' · ') || 'Current market read';
    els.todayRadarCopy.textContent = a.radar.sectors.length || a.radar.tickers.length ? 'Your selected sectors and names stay close to the desk.' : 'Start with the desk’s current read, then make the first signal yours.';
    els.todayNextTitle.textContent = a.goal === 'holdings' ? 'Confirm one holding.' : a.goal === 'learn' ? 'Open your first lesson.' : 'Save one name from Today.';
    els.todayNextCopy.textContent = 'One meaningful action is enough to make this desk yours.';
    var lesson = lessonFor(a);
    els.todayLessonTitle.textContent = lesson[0] + '.';
    els.todayLessonCopy.textContent = lesson[1];
    try{ els.todayResume.hidden = !localStorage.getItem('henneth-onboarding-draft'); }catch(err){ els.todayResume.hidden = true; }
    els.rightPanel.classList.remove('calibrating');
    var finalStatus = a.lens === 'fundamentals' ? 'Your value lens is ready' : a.goal === 'market' ? 'Your market radar is online' : a.goal === 'learn' ? 'Your learning path is ready' : 'Your research desk is prepared';
    setTerminalStatus(finalStatus, 100);
    els.logLine1.innerHTML = '~/henneth-desk &gt; evidence recovered · radar indexed · lens calibrated';
    if (els.sealTextPath) els.sealTextPath.textContent = 'DESK PREPARED · PSX RESEARCH · YOUR LENS · RESEARCH NOT ADVICE · ';
    if(hasGSAP){ gsap.fromTo(els.todayShell,{opacity:0,y:10},{opacity:1,y:0,duration:.35,ease:'power2.out'}); } else { els.todayShell.style.opacity=1; els.todayShell.style.transform='none'; }
  }

  function wireOnboardingActions(){
    els.onboardingNext = document.getElementById('onboardingNext');
    els.onboardingBack = document.getElementById('onboardingBack');
    els.onboardingSkip = document.getElementById('onboardingSkip');
    els.onboardingSave = document.getElementById('onboardingSave');
    els.onboardingNext.addEventListener('click', function(){ if(els.onboardingNext.disabled) return; if(state.onboardingStep < 3){ state.onboardingStep += 1; renderOnboardingStep(); } else { prepareDesk(); } });
    if (els.onboardingBack) els.onboardingBack.addEventListener('click', function(){ if(state.onboardingStep === 0) return; state.onboardingStep -= 1; renderOnboardingStep(); var key=onboardingQuestions[state.onboardingStep].key; if(state.onboardingAnswers[key]) applyOnboardingSignal(key,state.onboardingAnswers[key]); persistOnboarding(); });
    els.onboardingSkip.addEventListener('click', function(){ state.onboarded=true; state.onboardingAnswers={goal:'everything',lens:'balanced',horizon:'figuring',radar:{sectors:[],tickers:[],source:'market-read'}}; localStorage.setItem('henneth-onboarding-skipped','1'); finishOnboarding('skipped'); returnToSurface(showToday); });
    els.onboardingSave.addEventListener('click', function(){ persistOnboarding(); state.onboarded=true; finishOnboarding('saved'); returnToSurface(showToday); });
    var know = document.getElementById('onboardingKnow');
    if(know) know.addEventListener('click', function(){ state.onboarded=true; state.onboardingAnswers={goal:'everything',lens:'balanced',horizon:'figuring',radar:{sectors:[],tickers:[],source:'market-read'}}; localStorage.removeItem('henneth-onboarding-draft'); finishOnboarding('skipped'); returnToSurface(showToday); });
  }
  wireOnboardingActions();

  els.todayResume.addEventListener('click', function(){ state.onboarded=false; els.todayResume.hidden=true; startOnboarding(); });

  var checkBoxes = Array.prototype.slice.call(els.checklist.querySelectorAll('input[type="checkbox"]'));
  function paintChecklist(){
    var count = checkBoxes.filter(function(b){ return b.checked; }).length;
    els.checklist.querySelector('summary').textContent =
      'Keep the momentum · ' + count + ' of ' + checkBoxes.length + ' complete';
  }
  try{
    var savedChecks = JSON.parse(localStorage.getItem('henneth-checklist') || '[]');
    checkBoxes.forEach(function(b){ b.checked = savedChecks.indexOf(b.getAttribute('data-check')) !== -1; });
  }catch(err){}
  paintChecklist();
  checkBoxes.forEach(function(box){
    box.addEventListener('change', function(){
      paintChecklist();
      try{ localStorage.setItem('henneth-checklist', JSON.stringify(checkBoxes.filter(function(b){ return b.checked; }).map(function(b){ return b.getAttribute('data-check'); }))); }catch(err){}
    });
  });

  els.enterDesk.addEventListener('click', function(){
    if (hooks.onEnterDesk) hooks.onEnterDesk();
  });

  /* ---------- ticker <-> map hover linking ---------- */
  function clearHighlights(){
    els.universeGroup.querySelectorAll('.hn-edge').forEach(function(e){ e.classList.remove('hn-hot','hn-dim'); });
    els.universeGroup.querySelectorAll('.hn-node').forEach(function(n){ n.classList.remove('hn-hot'); });
    els.universeGroup.querySelectorAll('.hn-label').forEach(function(l){ l.classList.remove('hn-hot','hn-dim'); });
  }

  function highlightSymbol(sym){
    els.universeGroup.querySelectorAll('.hn-edge').forEach(function(e){
      if (e.classList.contains('hn-act1')) return;
      var syms = (e.getAttribute('data-syms') || '').split(',');
      if (syms.indexOf(sym) !== -1){ e.classList.add('hn-hot'); }
      else { e.classList.add('hn-dim'); }
    });
    var node = document.getElementById('node-' + sym);
    var label = document.getElementById('label-' + sym);
    if (node) node.classList.add('hn-hot');
    if (label) label.classList.add('hn-hot');
    els.universeGroup.querySelectorAll('.hn-label').forEach(function(l){
      if (l.getAttribute('data-sym') !== sym) l.classList.add('hn-dim');
    });
  }

  els.tickerGrid.querySelectorAll('.cell').forEach(function(cell){
    var sym = cell.getAttribute('data-sym');
    cell.setAttribute('tabindex', '0');
    cell.setAttribute('aria-label', sym + ' market movement');
    cell.addEventListener('mouseenter', function(){
      cell.classList.add('hn-hot');
      highlightSymbol(sym);
    });
    cell.addEventListener('mouseleave', function(){
      cell.classList.remove('hn-hot');
      clearHighlights();
    });
    cell.addEventListener('focus', function(){
      cell.classList.add('hn-hot');
      highlightSymbol(sym);
    });
    cell.addEventListener('blur', function(){
      cell.classList.remove('hn-hot');
      clearHighlights();
    });
  });

  /* ---------- subtle parallax on right panel ---------- */
  if (!reduceMotion){
    var rect = null;
    function updateRect(){ rect = els.rightPanel.getBoundingClientRect(); }
    updateRect();
    window.addEventListener('resize', updateRect);

    var raf = null;
    var targetX = 0, targetY = 0, curX = 0, curY = 0;

    els.rightPanel.addEventListener('mousemove', function(e){
      if (!rect) updateRect();
      var mx = ((e.clientX - rect.left) / Math.max(rect.width, 1) - 0.5) * 2;
      var my = ((e.clientY - rect.top) / Math.max(rect.height, 1) - 0.5) * 2;
      targetX = mx; targetY = my;
      if (!raf) raf = requestAnimationFrame(tick);
    });
    els.rightPanel.addEventListener('mouseleave', function(){
      targetX = 0; targetY = 0;
      if (!raf) raf = requestAnimationFrame(tick);
    });

    function tick(){
      curX += (targetX - curX) * 0.08;
      curY += (targetY - curY) * 0.08;
      var boardX = curX * 6, boardY = curY * 4;
      var lineX = curX * 12, lineY = curY * 9;
      var sealX = curX * 3, sealY = curY * 2.5;

      els.board.style.transform = 'translate(' + boardX + 'px,' + boardY + 'px) scale(1)';
      els.universeGroup.style.transform = 'translate(' + lineX + 'px,' + lineY + 'px)';
      els.seal.style.transform = 'translate(' + sealX + 'px,' + sealY + 'px)';

      if (Math.abs(targetX - curX) > 0.001 || Math.abs(targetY - curY) > 0.001){
        raf = requestAnimationFrame(tick);
      } else {
        raf = null;
      }
    }
  }

  function countUp(el, from, to, suffix, duration){
    var start = null;
    function easeOutExpo(t){ return t === 1 ? 1 : 1 - Math.pow(2, -10 * t); }
    function step(ts){
      if (!start) start = ts;
      var t = Math.min((ts - start) / duration, 1);
      var eased = easeOutExpo(t);
      var val = from + (to - from) * eased;
      var sign = val >= 0 ? '+' : '';
      el.textContent = sign + val.toFixed(1) + suffix;
      if (t < 1) requestAnimationFrame(step);
      else { var s2 = to >= 0 ? '+' : ''; el.textContent = s2 + to.toFixed(1) + suffix; }
    }
    requestAnimationFrame(step);
  }

  function countUpPlain(el, from, to, duration, onDone){
    var start = null;
    function step(ts){
      if (!start) start = ts;
      var t = Math.min((ts - start) / duration, 1);
      var val = Math.round(from + (to - from) * t);
      el.textContent = val + '%';
      el.setAttribute('aria-valuenow', String(val));
      if (t < 1) requestAnimationFrame(step);
      else { el.textContent = to + '%'; el.setAttribute('aria-valuenow', String(to)); if (onDone) onDone(); }
    }
    requestAnimationFrame(step);
  }

  /* ---------- idle post-story ticker drift (subtle, secondary — never the main event) ---------- */
  function driftTickers(){
    var i = Math.floor(Math.random() * tickers.length);
    var t = tickers[i];
    var delta = (Math.random() * 0.3 - 0.12);
    var next = t.val + delta;
    var el = document.getElementById('chg-' + t.sym);
    if (!el) return;
    var cell = el.closest('.cell');
    if (reduceMotion){
      t.val = next;
      t.up = next >= 0;
      el.textContent = (next >= 0 ? '+' : '') + next.toFixed(1) + '%';
      el.classList.toggle('up', t.up);
      el.classList.toggle('down', !t.up);
      return;
    }
    if (cell) { cell.style.transform = 'translateY(-2px)'; setTimeout(function(){ cell.style.transform = ''; }, 380); }
    countUp(el, t.val, next, '%', 420);
    t.val = next;
    t.up = next >= 0;
    setTimeout(function(){
      el.classList.toggle('up', t.up);
      el.classList.toggle('down', !t.up);
    }, 430);
  }
  var driftInterval = null;

  /* ---------- Act 1 → Act 2 → Act 3 boot sequence ---------- */
  function boot(){
    paintTab(state.tab, { silent: true });
    updateSealText(state.tab);

    if (reduceMotion || !hasGSAP){
      /* skip the story entirely, show final composed state */
      els.formWrap.style.opacity = 1;
      els.formWrap.style.transform = 'none';
      els.evidenceLayer.style.display = 'none';
      els.seal.style.opacity = 1;
      els.sealRing.classList.add('spin');
      els.board.style.opacity = 1;
      els.board.style.transform = 'none';
      els.statusLine.innerHTML = 'Research terminal ready';
      els.statusLine.style.opacity = 1;
      els.statusPct.textContent = '100%';
      els.statusPct.setAttribute('aria-valuenow', '100');
      els.statusPct.style.opacity = 1;
      els.pathFill.style.width = '100%';
      els.boardLog.style.opacity = 1;
      els.logLine1.innerHTML = '~/henneth-desk &gt; universe ready · 15 names indexed';
      els.modulesDock.querySelectorAll('.module').forEach(function(m){ m.style.opacity = 1; m.style.transform = 'none'; });
      els.universeGroup.querySelectorAll('.hn-edge').forEach(function(e){ e.style.strokeDashoffset = 0; e.style.animation = 'none'; if (e.classList.contains('hn-act1')) e.style.opacity = 0; });
      els.universeGroup.querySelectorAll('.hn-node').forEach(function(n){ n.style.opacity = n.classList.contains('hn-node-lit') ? '1' : '.32'; n.style.animation = 'none'; });
      els.universeGroup.querySelectorAll('.hn-label').forEach(function(l){ l.style.opacity = '.68'; l.style.animation = 'none'; });
      els.universeGroup.querySelectorAll('.hn-pulse').forEach(function(p){ p.style.animation = 'none'; p.style.opacity = '0'; });
      tickers.forEach(function(t){ var el = document.getElementById('chg-' + t.sym); if (el) el.textContent = (t.val>=0?'+':'') + t.val.toFixed(1) + '%'; });
      return;
    }

    var evFrags = els.evidenceLayer.querySelectorAll('.ev-frag');
    var act1Edges = els.universeGroup.querySelectorAll('.hn-act1');
    var modules = els.modulesDock.querySelectorAll('.module');
    var cells = els.tickerGrid.querySelectorAll('.cell');

    var tl = gsap.timeline({
      defaults: { ease: 'power2.out' },
      onComplete: function(){
        els.ctaBtn.classList.add('ready-pulse');
        setTimeout(function(){ els.ctaBtn.classList.remove('ready-pulse'); }, 900);
        /* Idle state stays still; movement is reserved for intentional state changes. */
      }
    });

    /* ACT 1 — market noise / uncertainty (0.0s–1.2s) */
    tl.to(els.formWrap, { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' }, 0)
      .to(els.statusLine, { opacity: 1, duration: 0.3 }, 0.05)
      .to(els.statusPct, { opacity: 1, duration: 0.3 }, 0.05)
      .fromTo(evFrags,
        { opacity: 0, y: -4 },
        { opacity: 1, y: 0, duration: 0.32, stagger: 0.09, ease: 'power1.out' },
        0.15)
      .call(function(){ countUpPlain(els.statusPct, 0, 21, 500); }, null, 0.2)
      .to({}, { duration: 0.05 }, 1.15); /* hold beat before act 2 begins */

    /* ACT 2 — the desk organizes the evidence (1.2s–3.4s) */
    tl.to(evFrags, { opacity: 0, duration: 0.35, stagger: 0.02, ease: 'power1.in' }, 1.2)
      .call(function(){
        els.statusLine.innerHTML = 'Assembling the board' + '<span class="caret"></span>';
      }, null, 1.25)
      .to(els.pathFill, { width: '21%', duration: 0.3, ease: 'power1.out' }, 1.25)
      .to(els.board, { opacity: 1, y: 0, scale: 1, duration: 0.5, ease: 'back.out(1.3)' }, 1.4)
      .call(function(){ countUpPlain(els.statusPct, 21, 64, 700); }, null, 1.45)
      .to(els.pathFill, { width: '64%', duration: 0.7, ease: 'power2.out' }, 1.45)
      .fromTo(cells,
        { opacity: 0, y: 6 },
        { opacity: 1, y: 0, duration: 0.35, stagger: 0.028, ease: 'power2.out' },
        1.55)
      .call(function(){
        tickers.forEach(function(t){
          var el = document.getElementById('chg-' + t.sym);
          if (el) countUp(el, 0, t.val, '%', 500);
        });
      }, null, 1.6)
      .call(function(){
        els.statusLine.innerHTML = 'Indexing research modules' + '<span class="caret"></span>';
      }, null, 2.2)
      .fromTo(modules,
        { opacity: 0, y: 8 },
        { opacity: 1, y: 0, duration: 0.32, stagger: 0.11, ease: 'power2.out' },
        2.3)
      .to(els.boardLog, { opacity: 1, duration: 0.3 }, 2.35);

    /* ACT 3 — access ready / terminal settles (3.4s–4.4s) */
    tl.call(function(){ countUpPlain(els.statusPct, 64, 100, 500); }, null, 3.4)
      .to(els.pathFill, { width: '100%', duration: 0.5, ease: 'power2.out' }, 3.4)
      .call(function(){
        els.statusLine.innerHTML = 'Research terminal ready';
        els.logLine1.innerHTML = '~/henneth-desk &gt; universe ready · 15 names indexed';
      }, null, 3.75)
      .to(els.board, { x: 0, y: -2, duration: 0.3, ease: 'power1.out' }, 3.85)
      .to(els.board, { y: 0, duration: 0.25, ease: 'power2.out' }, 4.15)
      .to(act1Edges, { opacity: 0, duration: 0.3 }, 3.4)
      .to(els.seal, { opacity: 1, duration: 0.4 }, 3.9)
      .call(function(){ els.sealRing.classList.add('spin'); }, null, 4.0)
      .to(els.ctaBtn, { boxShadow: '0 0 0 3px rgba(0,168,132,.18)', duration: 0.3 }, 4.0);
  }

    /* --- boot + handles for the host app (replaces the design's DOMContentLoaded) --- */
    boot();
    return {
      root: root,
      els: els,
      state: state,
      paintTab: paintTab,
      switchTab: switchTab,
      startOnboarding: startOnboarding,
      showToday: showToday,
      /* The host writes the radar into the real watchlist, so it needs the resolved symbols —
         the sector -> symbol map lives here and must not be duplicated in app.js. */
      radarSymbols: radarSymbols,
      setTerminalStatus: setTerminalStatus,
      setErr: setErr,
      clearErrors: clearErrors,
      setMsg: setMsg,
      setBusy: setBusy,
      hooks: hooks
    };
  }

  window.HennethAuthTerminal = { mount: mount, unmount: unmount };
})();
