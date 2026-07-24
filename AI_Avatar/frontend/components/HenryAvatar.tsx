import { forwardRef } from 'react';

export interface HenryAvatarProps {
  width: number;
  height: number;
  label?: string;
  status?: 'loading' | 'ready' | 'error';
}

export const HenryAvatar = forwardRef<HTMLCanvasElement, HenryAvatarProps>(
  function HenryAvatar(
    {
      width,
      height,
      label = 'Henry AI Avatar animation',
      status = 'loading',
    },
    ref,
  ) {
    return (
      <div className="henry-avatar" data-status={status}>
        <div className="henry-avatar__halo" aria-hidden="true" />
        <canvas
          ref={ref}
          width={width}
          height={height}
          role="img"
          aria-label={label}
        />
      </div>
    );
  },
);
