/**
 * Logo — THESYS+ branding logo component
 * 
 * Simple text-based logo with gradient styling for the THESYS+ brand.
 * Used in authentication pages and headers.
 */

export default function Logo({ className = '' }) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <h1 className="text-3xl font-bold">
        <span className="bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">
          THESYS
        </span>
        <span className="text-purple-600">+</span>
      </h1>
    </div>
  );
}
