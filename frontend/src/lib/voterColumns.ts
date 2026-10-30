import type { ColumnKey, VoterSchema } from '../types'

export const columnLabels: Record<ColumnKey, string> = {
  name: 'Name',
  rollNo: 'Roll no.',
  email: 'Email',
  phone: 'Phone',
}

/** Header names expected in an uploaded CSV / Excel file. */
export const columnHeaders: Record<ColumnKey, string> = {
  name: 'name',
  rollNo: 'roll_no',
  email: 'email',
  phone: 'phone',
}

/** Columns that must be present for every voter, derived from the organiser's choices. */
export function mandatoryColumns(schema: VoterSchema): ColumnKey[] {
  const cols: ColumnKey[] = [...schema.identityColumns]
  if (schema.otpChannels.includes('email')) cols.push('email')
  if (schema.otpChannels.includes('phone')) cols.push('phone')
  const order: ColumnKey[] = ['name', 'rollNo', 'email', 'phone']
  return order.filter((c) => cols.includes(c))
}
