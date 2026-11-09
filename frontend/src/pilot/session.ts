import type { CaseId } from '../api/evidenceToAction';
import type { QuestionId } from './questions';
import schedule from './schedule.json';

export const protocol = 'bp16-pilot-v1';
export const baseline = 'ab99ff28c99be9fc93e4fab6abc2748e2b7fd904';
type Condition = 'signal-only' | 'evidence-to-action';
export type Task = { case_id: CaseId; condition: Condition; position: number };
export type Choices = Record<QuestionId, number>;
export type Response = Task & {
  anomaly: string;
  choices: Choices;
  elapsed_ms: number;
  interrupted: boolean;
};

export function getSequence(value: string | null): number | undefined {
  return value && /^[1-8]$/.test(value) ? Number(value) : undefined;
}

export function getTasks(sequence: number): Task[] {
  const index = sequence - 1;
  const order = schedule.orders[Math.floor(index / 2)] as CaseId[];
  const conditions = schedule.conditions[index % 2] as Condition[];
  return order.map((case_id, offset) => ({
    case_id,
    condition: conditions[offset],
    position: offset + 1,
  }));
}

export function downloadResponses(sessionId: string, sequence: number, responses: Response[]) {
  const record = { protocol, baseline, session_id: sessionId, sequence, responses };
  const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2) + '\n'], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `bp16-response-${sessionId}.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
