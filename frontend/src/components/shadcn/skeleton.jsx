import { cn } from '@/lib/utils';

function Skeleton({ className, ...props }) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted-surface', className)}
      {...props}
    />
  );
}

export { Skeleton };
