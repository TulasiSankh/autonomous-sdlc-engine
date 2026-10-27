import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PlanCard } from '../components/PlanCard';
import type { Plan } from '../types/api';

describe('PlanCard component', () => {
  const mockPlan: Plan = {
    task: 'Add authentication middleware',
    summary: 'Strategic execution plan for authentication',
    steps: [
      '1. Create auth router',
      '2. Implement JWT token validation',
      '3. Add security middleware',
    ],
    files_to_inspect: ['api/main.py', 'api/routes/'],
    acceptance_criteria: ['All routes protected', 'Zero regressions'],
    tests_to_run: ['pytest tests/test_auth.py -v'],
    risks: ['Token expiration edge cases', 'Performance latency'],
  };

  it('renders all sections of the structured plan', () => {
    render(<PlanCard plan={mockPlan} />);

    expect(screen.getByTestId('plan-card')).toBeDefined();
    expect(screen.getByText('Strategic execution plan for authentication')).toBeDefined();

    // Steps
    expect(screen.getByText('1. Create auth router')).toBeDefined();
    expect(screen.getByText('2. Implement JWT token validation')).toBeDefined();
    expect(screen.getByText('3. Add security middleware')).toBeDefined();

    // Files
    expect(screen.getByText('api/main.py')).toBeDefined();
    expect(screen.getByText('api/routes/')).toBeDefined();

    // Acceptance criteria
    expect(screen.getByText('All routes protected')).toBeDefined();

    // Verification commands
    expect(screen.getByText('$ pytest tests/test_auth.py -v')).toBeDefined();

    // Risks
    expect(screen.getByText('Token expiration edge cases')).toBeDefined();
  });
});
