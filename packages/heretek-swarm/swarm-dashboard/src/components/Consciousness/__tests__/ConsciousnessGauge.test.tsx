/**
 * ConsciousnessGauge component tests
 *
 * Verifies SVG gauge rendering, label display, value clamping, tooltip hover behavior,
 * and the animated CSS class toggle.
 */

import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ConsciousnessGauge } from '../ConsciousnessGauge';

afterEach(() => {
  cleanup();
});

describe('ConsciousnessGauge', () => {
  it('renders an SVG with the given size', () => {
    const { container } = render(<ConsciousnessGauge size={300} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute('width', '300');
    expect(svg).toHaveAttribute('height', '300');
  });

  it('displays all four theory labels when showLabels is true', () => {
    const { container } = render(
      <ConsciousnessGauge
        gwtValue={50}
        iitValue={60}
        astValue={70}
        fepValue={80}
        showLabels
      />
    );
    // Labels are SVG text elements — query by container
    const svgText = container.querySelectorAll('text');
    const texts = Array.from(svgText).map(t => t.textContent);
    expect(texts).toContain('GWT');
    expect(texts).toContain('IIT');
    expect(texts).toContain('AST');
    expect(texts).toContain('FEP');
  });

  it('hides labels when showLabels is false', () => {
    const { container } = render(<ConsciousnessGauge showLabels={false} />);
    const svgText = container.querySelectorAll('text');
    const texts = Array.from(svgText).map(t => t.textContent);
    // The center "Average" text should still be present
    expect(texts).toContain('Average');
    // But theory labels should not appear
    expect(texts).not.toContain('GWT');
    expect(texts).not.toContain('IIT');
    expect(texts).not.toContain('AST');
    expect(texts).not.toContain('FEP');
  });

  it('renders the average value in the center', () => {
    const { container } = render(
      <ConsciousnessGauge gwtValue={50} iitValue={50} astValue={50} fepValue={50} />
    );
    const svgText = container.querySelectorAll('text');
    const texts = Array.from(svgText).map(t => t.textContent);
    expect(texts).toContain('50.0');
  });

  it('clamps values above 100 to 100', () => {
    const { container } = render(
      <ConsciousnessGauge gwtValue={150} iitValue={200} astValue={100} fepValue={0} />
    );
    const svgText = container.querySelectorAll('text');
    const texts = Array.from(svgText).map(t => t.textContent);
    // (100 + 100 + 100 + 0) / 4 = 75.0
    expect(texts).toContain('75.0');
  });

  it('clamps negative values to 0', () => {
    const { container } = render(
      <ConsciousnessGauge gwtValue={-10} iitValue={-5} astValue={0} fepValue={100} />
    );
    const svgText = container.querySelectorAll('text');
    const texts = Array.from(svgText).map(t => t.textContent);
    // (0 + 0 + 0 + 100) / 4 = 25.0
    expect(texts).toContain('25.0');
  });

  it('applies animated CSS class by default', () => {
    const { container } = render(
      <ConsciousnessGauge gwtValue={50} iitValue={50} astValue={50} fepValue={50} animated />
    );
    const filledPaths = container.querySelectorAll('path[style*="cursor: pointer"]');
    const hasTransition = Array.from(filledPaths).some((p) =>
      p.className.baseVal?.includes('transition-all')
    );
    expect(hasTransition).toBe(true);
  });

  it('does not apply animated CSS class when animated is false', () => {
    const { container } = render(
      <ConsciousnessGauge gwtValue={50} iitValue={50} astValue={50} fepValue={50} animated={false} />
    );
    const filledPaths = container.querySelectorAll('path[style*="cursor: pointer"]');
    const hasTransition = Array.from(filledPaths).some((p) =>
      p.className.baseVal?.includes('transition-all')
    );
    expect(hasTransition).toBe(false);
  });

  it('shows tooltip on hover and hides on mouse leave', () => {
    const { container } = render(
      <ConsciousnessGauge gwtValue={80} iitValue={60} astValue={40} fepValue={20} />
    );
    const filledPaths = container.querySelectorAll('path[style*="cursor: pointer"]');
    expect(filledPaths.length).toBeGreaterThan(0);

    fireEvent.mouseEnter(filledPaths[0]);
    const tooltip = container.querySelector('.pointer-events-none.z-10');
    expect(tooltip).toBeInTheDocument();

    fireEvent.mouseLeave(filledPaths[0]);
    expect(container.querySelector('.pointer-events-none.z-10')).not.toBeInTheDocument();
  });

  it('renders with default zero values when no props provided', () => {
    const { container } = render(<ConsciousnessGauge />);
    const svgText = container.querySelectorAll('text');
    const texts = Array.from(svgText).map(t => t.textContent);
    expect(texts).toContain('0.0');
    expect(texts).toContain('Average');
  });

  it('includes per-segment numeric values when labels are shown', () => {
    const { container } = render(
      <ConsciousnessGauge gwtValue={42} iitValue={88} astValue={15} fepValue={67} showLabels />
    );
    const svgText = container.querySelectorAll('text');
    const texts = Array.from(svgText).map(t => t.textContent);
    expect(texts).toContain('42');
    expect(texts).toContain('88');
    expect(texts).toContain('15');
    expect(texts).toContain('67');
  });
});
