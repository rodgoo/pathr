/**
 * The segmented control, on native radios.
 *
 * Nocturne styles `.seg` / `.seg-opt` entirely from the checked state of the
 * input inside, so arrow-key navigation, focus and the accent ring all come
 * for free. The label is the control; the input stays in the accessibility
 * tree but is visually collapsed by the stylesheet.
 */
import type { CSSProperties } from "react";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentedProps<T extends string> {
  /** Radio group name — must be unique on the page. */
  name: string;
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  /** Names the group for assistive tech when no visible label sits beside it. */
  label: string;
  style?: CSSProperties;
}

export function Segmented<T extends string>({
  name,
  options,
  value,
  onChange,
  label,
  style,
}: SegmentedProps<T>) {
  return (
    <span className="seg" role="radiogroup" aria-label={label} style={style}>
      {options.map((option) => (
        <label key={option.value} className="seg-opt">
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
          {option.label}
        </label>
      ))}
    </span>
  );
}
