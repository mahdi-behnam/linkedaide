"""Advanced Behavioral Biometrics controller for realistic human browser interaction."""

from __future__ import annotations

import asyncio
import logging
import math
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

logger = logging.getLogger(__name__)

# Standard QWERTY keyboard physical coordinates: (row, col, hand: 'L'|'R'|'B')
QWERTY_COORDS: dict[str, tuple[float, float, str]] = {
    # Number row
    "1": (0.0, 0.0, "L"),
    "2": (0.0, 1.0, "L"),
    "3": (0.0, 2.0, "L"),
    "4": (0.0, 3.0, "L"),
    "5": (0.0, 4.0, "L"),
    "6": (0.0, 5.0, "R"),
    "7": (0.0, 6.0, "R"),
    "8": (0.0, 7.0, "R"),
    "9": (0.0, 8.0, "R"),
    "0": (0.0, 9.0, "R"),
    "-": (0.0, 10.0, "R"),
    "=": (0.0, 11.0, "R"),
    # Top row
    "q": (1.0, 0.5, "L"),
    "w": (1.0, 1.5, "L"),
    "e": (1.0, 2.5, "L"),
    "r": (1.0, 3.5, "L"),
    "t": (1.0, 4.5, "L"),
    "y": (1.0, 5.5, "R"),
    "u": (1.0, 6.5, "R"),
    "i": (1.0, 7.5, "R"),
    "o": (1.0, 8.5, "R"),
    "p": (1.0, 9.5, "R"),
    "[": (1.0, 10.5, "R"),
    "]": (1.0, 11.5, "R"),
    # Home row
    "a": (2.0, 0.8, "L"),
    "s": (2.0, 1.8, "L"),
    "d": (2.0, 2.8, "L"),
    "f": (2.0, 3.8, "L"),
    "g": (2.0, 4.8, "L"),
    "h": (2.0, 5.8, "R"),
    "j": (2.0, 6.8, "R"),
    "k": (2.0, 7.8, "R"),
    "l": (2.0, 8.8, "R"),
    ";": (2.0, 9.8, "R"),
    "'": (2.0, 10.8, "R"),
    # Bottom row
    "z": (3.0, 1.2, "L"),
    "x": (3.0, 2.2, "L"),
    "c": (3.0, 3.2, "L"),
    "v": (3.0, 4.2, "L"),
    "b": (3.0, 5.2, "L"),
    "n": (3.0, 6.2, "R"),
    "m": (3.0, 7.2, "R"),
    ",": (3.0, 8.2, "R"),
    ".": (3.0, 9.2, "R"),
    "/": (3.0, 10.2, "R"),
    # Space
    " ": (4.0, 4.5, "B"),
}

# Physical adjacent keys on standard QWERTY for emulating natural typos
ADJACENT_KEYS: dict[str, list[str]] = {
    "a": ["q", "w", "s", "z"],
    "b": ["v", "g", "h", "n"],
    "c": ["x", "d", "f", "v"],
    "d": ["s", "e", "r", "f", "c", "x"],
    "e": ["w", "s", "d", "r", "3", "4"],
    "f": ["d", "r", "t", "g", "v", "c"],
    "g": ["f", "t", "y", "h", "b", "v"],
    "h": ["g", "y", "u", "j", "n", "b"],
    "i": ["u", "j", "k", "o", "8", "9"],
    "j": ["h", "u", "i", "k", "m", "n"],
    "k": ["j", "i", "o", "l", "m"],
    "l": ["k", "o", "p", ";"],
    "m": ["n", "j", "k"],
    "n": ["b", "h", "j", "m"],
    "o": ["i", "k", "l", "p", "9", "0"],
    "p": ["o", "l", "[", "0", "-"],
    "q": ["1", "2", "w", "a"],
    "r": ["e", "d", "f", "t", "4", "5"],
    "s": ["a", "w", "e", "d", "x", "z"],
    "t": ["r", "f", "g", "y", "5", "6"],
    "u": ["y", "h", "j", "i", "7", "8"],
    "v": ["c", "d", "f", "g", "b"],
    "w": ["q", "a", "s", "e", "2", "3"],
    "x": ["z", "a", "s", "d", "c"],
    "y": ["t", "g", "h", "u", "6", "7"],
    "z": ["a", "s", "x"],
}

PUNCTUATION_PAUSES: frozenset[str] = frozenset({".", ",", "!", "?", "\n", ";", ":"})


class BiometricController:
    """Controls cursor motion, element clicks, keystroke timing, and scrolling with biological fidelity."""

    def __init__(self, page: Page, delay_scale: float = 1.0) -> None:
        self.page = page
        self.delay_scale = max(0.01, delay_scale)
        self._current_x: float = 100.0
        self._current_y: float = 100.0

    async def _dispatch_mouse_move(self, x: float, y: float) -> None:
        mouse = getattr(self.page, "mouse", None)
        if mouse and hasattr(mouse, "move"):
            res = mouse.move(x, y)
            if hasattr(res, "__await__"):
                await res

    async def _dispatch_mouse_down(self) -> None:
        mouse = getattr(self.page, "mouse", None)
        if mouse and hasattr(mouse, "down"):
            res = mouse.down()
            if hasattr(res, "__await__"):
                await res

    async def _dispatch_mouse_up(self) -> None:
        mouse = getattr(self.page, "mouse", None)
        if mouse and hasattr(mouse, "up"):
            res = mouse.up()
            if hasattr(res, "__await__"):
                await res

    async def _dispatch_mouse_wheel(self, delta_x: float, delta_y: float) -> None:
        mouse = getattr(self.page, "mouse", None)
        if mouse and hasattr(mouse, "wheel"):
            res = mouse.wheel(delta_x, delta_y)
            if hasattr(res, "__await__"):
                await res

    async def _dispatch_key(self, locator: Locator, key: str) -> None:
        if hasattr(locator, "press_sequentially"):
            res = locator.press_sequentially(key)
            if hasattr(res, "__await__"):
                await res
        elif hasattr(locator, "press"):
            res = locator.press(key)
            if hasattr(res, "__await__"):
                await res
        elif hasattr(self.page, "keyboard") and hasattr(self.page.keyboard, "type"):
            res = self.page.keyboard.type(key)
            if hasattr(res, "__await__"):
                await res

    async def _dispatch_backspace(self, locator: Locator) -> None:
        if hasattr(locator, "press"):
            res = locator.press("Backspace")
            if hasattr(res, "__await__"):
                await res
        elif hasattr(self.page, "keyboard") and hasattr(self.page.keyboard, "press"):
            res = self.page.keyboard.press("Backspace")
            if hasattr(res, "__await__"):
                await res

    async def move_to(
        self,
        target_x: float,
        target_y: float,
        steps: int = 25,
        target_width: float = 50.0,
    ) -> None:
        """Trace Cubic Bézier curve with Fitts's law duration and sigmoidal velocity profile.

        Cubic Bézier formula:
            B(t) = (1-t)^3 P_0 + 3(1-t)^2 t P_1 + 3(1-t) t^2 P_2 + t^3 P_3

        Args:
            target_x: Target X viewport coordinate.
            target_y: Target Y viewport coordinate.
            steps: Number of intermediate movement steps (default: 25).
            target_width: Width of target element for Fitts's law modeling.
        """
        p0_x, p0_y = self._current_x, self._current_y
        p3_x, p3_y = float(target_x), float(target_y)

        dx = p3_x - p0_x
        dy = p3_y - p0_y
        distance = math.hypot(dx, dy)

        if distance < 1.0 or steps <= 1:
            await self._dispatch_mouse_move(p3_x, p3_y)
            self._current_x = p3_x
            self._current_y = p3_y
            return

        # Unit vectors
        ux = dx / distance
        uy = dy / distance
        nx = -uy
        ny = ux

        # Randomized orthogonal control points simulating natural biological arm/wrist curvature
        arc_direction = random.choice([-1.0, 1.0])
        dev1 = arc_direction * random.uniform(0.10, 0.25)
        dev2 = arc_direction * random.uniform(0.08, 0.20) + random.uniform(-0.04, 0.04)

        u1 = random.uniform(0.25, 0.35)
        u2 = random.uniform(0.65, 0.75)

        p1_x = p0_x + dx * u1 + nx * distance * dev1
        p1_y = p0_y + dy * u1 + ny * distance * dev1
        p2_x = p0_x + dx * u2 + nx * distance * dev2
        p2_y = p0_y + dy * u2 + ny * distance * dev2

        # Fitts's Law duration modeling: T = a + b * log2(1 + D / W)
        effective_w = max(10.0, target_width)
        duration = 0.12 + 0.08 * math.log2(1.0 + distance / effective_w)
        duration = max(0.10, min(0.65, duration))

        # Sigmoidal velocity profile (Beta-distribution PDF peaking around t ~ 0.4)
        weights: list[float] = []
        for i in range(1, steps + 1):
            s = i / steps
            # Peak at s ~ 0.4 with slow start and corrective deceleration
            w = (s**1.5) * ((1.0 - s + 1e-5) ** 2.25)
            weights.append(max(1e-4, w))

        total_weight = sum(weights)
        t_values: list[float] = []
        accum_w = 0.0
        for w in weights:
            accum_w += w
            t_values.append(accum_w / total_weight)

        # Subtle Brownian micro-jitter
        jitter_x = 0.0
        jitter_y = 0.0
        step_sleep = (duration / steps) * self.delay_scale

        for i, t in enumerate(t_values):
            if i == steps - 1 or t >= 1.0:
                pt_x = p3_x
                pt_y = p3_y
            else:
                # Cubic Bézier interpolation
                om_t = 1.0 - t
                b_x = (
                    (om_t**3) * p0_x
                    + 3.0 * (om_t**2) * t * p1_x
                    + 3.0 * om_t * (t**2) * p2_x
                    + (t**3) * p3_x
                )
                b_y = (
                    (om_t**3) * p0_y
                    + 3.0 * (om_t**2) * t * p1_y
                    + 3.0 * om_t * (t**2) * p2_y
                    + (t**3) * p3_y
                )

                # Brownian micro-jitter damped at endpoints by parabolic envelope 4*t*(1-t)
                jitter_x += random.gauss(0.0, 0.4)
                jitter_y += random.gauss(0.0, 0.4)
                envelope = 4.0 * t * (1.0 - t)
                pt_x = b_x + jitter_x * envelope
                pt_y = b_y + jitter_y * envelope

            await self._dispatch_mouse_move(pt_x, pt_y)
            if step_sleep > 0.001:
                await asyncio.sleep(step_sleep)

        self._current_x = p3_x
        self._current_y = p3_y

    async def click_element(self, locator: Locator) -> None:
        """Click element using humanized targeting, pre-click dwell, and mouse contact dwell.

        Fallback to locator.click() if bounding box is not available.

        Args:
            locator: Target Playwright Locator.
        """
        box: dict[str, Any] | None = None
        bb_fn = getattr(locator, "bounding_box", None)
        if bb_fn is not None and callable(bb_fn):
            try:
                res = bb_fn()
                if hasattr(res, "__await__"):
                    box = await res
                elif isinstance(res, dict):
                    box = res
            except Exception:
                box = None

        if not box or box.get("width", 0) <= 0 or box.get("height", 0) <= 0:
            if hasattr(locator, "click"):
                res = locator.click()
                if hasattr(res, "__await__"):
                    await res
            return

        # Gaussian distribution clamped to [0.2, 0.8] inside bounding box
        rx = max(0.2, min(0.8, random.gauss(0.5, 0.12)))
        ry = max(0.2, min(0.8, random.gauss(0.5, 0.12)))

        target_x = box["x"] + rx * box["width"]
        target_y = box["y"] + ry * box["height"]
        target_width = min(box["width"], box["height"])

        await self.move_to(target_x, target_y, target_width=target_width)

        # Pre-click dwell (40-100ms)
        pre_dwell = random.uniform(0.040, 0.100) * self.delay_scale
        if pre_dwell > 0.001:
            await asyncio.sleep(pre_dwell)

        await self._dispatch_mouse_down()

        # Contact dwell (60-120ms)
        contact_dwell = random.uniform(0.060, 0.120) * self.delay_scale
        if contact_dwell > 0.001:
            await asyncio.sleep(contact_dwell)

        await self._dispatch_mouse_up()

    def _calculate_keystroke_interval(self, prev_char: str | None, curr_char: str) -> float:
        """Calculate log-normal keystroke interval with QWERTY digram penalty in seconds."""
        # Log-normal keystroke intervals (t ~ LN(4.6, 0.38), bounded 45ms to 300ms)
        raw_ms = random.lognormvariate(4.6, 0.38)

        # QWERTY digram modifier
        modifier = 1.0
        if prev_char is not None:
            c1_lower = prev_char.lower()
            c2_lower = curr_char.lower()
            if c1_lower in QWERTY_COORDS and c2_lower in QWERTY_COORDS:
                r1, col1, hand1 = QWERTY_COORDS[c1_lower]
                r2, col2, hand2 = QWERTY_COORDS[c2_lower]

                dist = math.hypot(r2 - r1, col2 - col1)
                if dist <= 1.5:
                    # Adjacent keys type faster
                    modifier = 0.82
                elif hand1 != hand2 and hand1 != "B" and hand2 != "B":
                    # Opposite hand alternation penalty / slight pause
                    modifier = 1.18
                elif c1_lower == c2_lower:
                    # Same key repeat
                    modifier = 0.75

        interval_ms = max(45.0, min(300.0, raw_ms * modifier))
        return (interval_ms / 1000.0) * self.delay_scale

    async def type_text(
        self,
        locator: Locator,
        text: str,
        typo_prob: float = 0.015,
    ) -> None:
        """Type text into target locator with log-normal intervals, QWERTY digram model, and typos.

        Args:
            locator: Target Playwright Locator.
            text: String text to type.
            typo_prob: Probability of emulating human typos (default: 0.015).
        """
        # Focus element (clicks if needed)
        try:
            if hasattr(locator, "focus"):
                res = locator.focus()
                if hasattr(res, "__await__"):
                    await res
            else:
                await self.click_element(locator)
        except Exception:
            try:
                await self.click_element(locator)
            except Exception:
                pass

        prev_char: str | None = None
        for char in text:
            # Emulate human typos with probability P = 0.015
            char_lower = char.lower()
            will_typo = (
                typo_prob > 0.0 and random.random() < typo_prob and char_lower in ADJACENT_KEYS
            )

            if will_typo:
                adjacent_candidate = random.choice(ADJACENT_KEYS[char_lower])
                typo_char = adjacent_candidate.upper() if char.isupper() else adjacent_candidate

                # Type adjacent typo key
                await self._dispatch_key(locator, typo_char)

                # Pause 120-250ms
                typo_pause = random.uniform(0.120, 0.250) * self.delay_scale
                if typo_pause > 0.001:
                    await asyncio.sleep(typo_pause)

                # Press Backspace
                await self._dispatch_backspace(locator)

                # Pause 50-100ms
                correct_pause = random.uniform(0.050, 0.100) * self.delay_scale
                if correct_pause > 0.001:
                    await asyncio.sleep(correct_pause)

            # Normal keystroke interval
            interval = self._calculate_keystroke_interval(prev_char, char)
            if interval > 0.001:
                await asyncio.sleep(interval)

            await self._dispatch_key(locator, char)
            prev_char = char

            # Cognitive pause (200-400ms) after punctuation (., !, ?, \n)
            if char in PUNCTUATION_PAUSES:
                cognitive_pause = random.uniform(0.200, 0.400) * self.delay_scale
                if cognitive_pause > 0.001:
                    await asyncio.sleep(cognitive_pause)

    async def smooth_wheel_scroll(self, total_pixels: int, steps: int = 8) -> None:
        """Emulate mouse wheel notches with inertial momentum decay and inter-notch pauses.

        Args:
            total_pixels: Total vertical pixels to scroll (positive: down, negative: up).
            steps: Number of scroll notches (default: 8).
        """
        if total_pixels == 0:
            return
        effective_steps = max(1, steps)

        # Inertial momentum decay weights: exponential decay over steps
        raw_weights = [math.exp(-0.4 * i) for i in range(effective_steps)]
        sum_weights = sum(raw_weights)
        normalized_weights = [w / sum_weights for w in raw_weights]

        accumulated = 0
        for i, weight in enumerate(normalized_weights):
            if i == effective_steps - 1:
                step_delta = total_pixels - accumulated
            else:
                step_delta = round(total_pixels * weight)
                accumulated += step_delta

            await self._dispatch_mouse_wheel(0.0, float(step_delta))

            # Inter-notch pause (30-70ms)
            pause = random.uniform(0.030, 0.070) * self.delay_scale
            if pause > 0.001:
                await asyncio.sleep(pause)
