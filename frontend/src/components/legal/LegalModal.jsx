/**
 * LegalModal — Reusable modal for Terms, Privacy Policy, and Help Center
 * Uses React Portal for proper z-index stacking
 */

import { createPortal } from 'react-dom';
import { useEffect } from 'react';
import useFocusTrap from '../../hooks/useFocusTrap';

export default function LegalModal({ isOpen, onClose, type, isDark }) {
  const panelRef = useFocusTrap(isOpen);
  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleEsc = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [isOpen, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  if (!isOpen) return null;

  const content = getContent(type);

  const modalContent = (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[9999] thesys-overlay-enter"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
        <div
          ref={panelRef}
          className="relative w-full max-w-3xl max-h-[85vh] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] overflow-hidden shadow-2xl thesys-modal-enter"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)] bg-[var(--color-surface-elevated)]/95 backdrop-blur-sm">
            <h2 className="text-xl font-bold text-ink">
              {content.title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 text-muted hover:text-ink hover:bg-[var(--color-icon-btn-hover-bg)]"
              aria-label="Close"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="overflow-y-auto px-6 py-6" style={{ maxHeight: 'calc(85vh - 80px)' }}>
            {/* Reading column: Source Serif 4 for legal prose body (Phase 2.C-2).
                font-reading = Source Serif 4 Variable, applied to this wrapper only.
                max-w-[65ch] constrains prose to the approved reading measure.
                text-[1.0625rem]/leading-[1.65] = 17px at 1.65 line-height.
                Prose headings (h3/h4) inside content.body carry their own
                Inter class names and override font-family at element level. */}
            <div
              className={`max-w-[65ch] font-reading text-[1.0625rem] leading-[1.65] ${isDark ? 'text-gray-200' : 'text-gray-800'}`}
              style={{ textWrap: 'pretty' }}
            >
              {content.body}
            </div>
          </div>
        </div>
      </div>
    </>
  );

  return createPortal(modalContent, document.body);
}

// Content for each modal type
function getContent(type) {
  if (type === 'about') {
    return {
      title: 'About THESYS+',
      body: (
        <>
          <p className="text-sm leading-relaxed mb-4">
            THESYS+ is a Semantic-Based Thesis Retrieval and Topic Trend Analysis System developed for Pampanga State University, College of Computing Studies. It preserves CCS undergraduate theses, makes them findable by meaning rather than exact keywords, and turns the accumulated body of student research into research intelligence.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">What THESYS+ Does</h3>
          <ul className="text-sm leading-relaxed mb-4 list-disc pl-5 space-y-1">
            <li>Semantic search across the CCS undergraduate thesis repository using SBERT embeddings</li>
            <li>Title originality validation against the full corpus using cosine similarity and TF-IDF</li>
            <li>Topic trend analysis that surfaces saturated, emerging, and underexplored research areas</li>
            <li>A structured submission and faculty review workflow for new theses</li>
            <li>Departmental analytics on research output over time</li>
          </ul>

          <h3 className="text-base font-semibold mt-6 mb-3">Methodology</h3>
          <p className="text-sm leading-relaxed mb-4">
            Semantic retrieval is powered by the all-MiniLM-L6-v2 sentence-transformer model, ranked by cosine similarity. Topic clusters are derived using TF-IDF feature extraction and K-Means clustering. These AI-assisted features are decision-support tools and do not replace consultation with faculty advisers.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Institutional Context</h3>
          <p className="text-sm leading-relaxed mb-4">
            THESYS+ is a departmental system owned and operated by Pampanga State University CCS. It covers CCS undergraduate theses across the BSIS, BSIT, and BSCS programs.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Contact</h3>
          <p className="text-sm leading-relaxed mb-4">
            For questions about THESYS+, please contact the system administrator at Pampanga State University, College of Computing Studies.
          </p>
        </>
      ),
    };
  }

  if (type === 'privacy') {
    return {
      title: 'Privacy Policy',
      body: (
        <>
          <p className="text-sm leading-relaxed mb-4">
            <strong>Effective Date:</strong> June 1, 2026
          </p>
          <p className="text-sm leading-relaxed mb-4">
            THESYS+ is a thesis retrieval and analysis system developed for Pampanga State University, College of Computing Studies. This Privacy Policy explains what information we collect, how we use it, and your rights regarding your data.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Information We Collect</h3>
          <p className="text-sm leading-relaxed mb-2">
            THESYS+ collects only the information necessary for account verification and repository use:
          </p>
          <ul className="text-sm leading-relaxed mb-4 list-disc pl-5 space-y-1">
            <li>Your name and PampangaStateU institutional email address</li>
            <li>Requested role (Student or Faculty)</li>
            <li>Uploaded verification documents (Student ID or Certificate of Registration)</li>
            <li>Thesis metadata (title, abstract, authors, keywords, program, year, adviser)</li>
            <li>Thesis documents uploaded to the repository</li>
            <li>Profile details (bio, interests, profile picture)</li>
            <li>Saved theses and search history</li>
            <li>System activity logs for security and troubleshooting</li>
          </ul>

          <h3 className="text-base font-semibold mt-6 mb-3">How We Use Your Information</h3>
          <p className="text-sm leading-relaxed mb-2">
            Your information is used for the following purposes:
          </p>
          <ul className="text-sm leading-relaxed mb-4 list-disc pl-5 space-y-1">
            <li>Verifying your eligibility as a PampangaStateU CCS student or faculty member</li>
            <li>Managing your account and providing access to THESYS+ features</li>
            <li>Managing the thesis repository and reviewing uploaded theses</li>
            <li>Enabling semantic search, title similarity validation, and topic trend analysis</li>
            <li>Generating analytics and insights about repository usage</li>
            <li>Improving system performance and user experience</li>
          </ul>

          <h3 className="text-base font-semibold mt-6 mb-3">Document Verification</h3>
          <p className="text-sm leading-relaxed mb-4">
            Uploaded verification documents (Student ID or Certificate of Registration) are used solely to confirm your PampangaStateU and CCS eligibility. These documents are processed using OCR technology and reviewed by administrators when necessary.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Thesis Review</h3>
          <p className="text-sm leading-relaxed mb-4">
            Thesis documents uploaded to THESYS+ may be reviewed by faculty or administrators before being published in the repository. This ensures the quality and appropriateness of content in the system.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Data Sharing</h3>
          <p className="text-sm leading-relaxed mb-4">
            THESYS+ does not sell, rent, or share your personal data with third parties. Your information is used exclusively within the THESYS+ system for the purposes described in this policy.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Data Security</h3>
          <p className="text-sm leading-relaxed mb-4">
            We implement appropriate technical and organizational measures to protect your data from unauthorized access, alteration, or disclosure. However, no system is completely secure, and we cannot guarantee absolute security.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Your Rights</h3>
          <p className="text-sm leading-relaxed mb-4">
            You have the right to access, update, or delete your personal information. If you have privacy-related concerns or wish to exercise your rights, please contact the THESYS+ system administrator.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Contact</h3>
          <p className="text-sm leading-relaxed mb-4">
            For questions or concerns about this Privacy Policy, please contact the THESYS+ administrator at Pampanga State University, College of Computing Studies.
          </p>
        </>
      ),
    };
  }

  if (type === 'terms') {
    return {
      title: 'Terms of Use',
      body: (
        <>
          <p className="text-sm leading-relaxed mb-4">
            <strong>Effective Date:</strong> June 1, 2026
          </p>
          <p className="text-sm leading-relaxed mb-4">
            By using THESYS+, you agree to comply with these Terms of Use. Please read them carefully before accessing or using the system.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Eligibility</h3>
          <p className="text-sm leading-relaxed mb-4">
            THESYS+ is available only to students and faculty members of Pampanga State University, College of Computing Studies. You must provide accurate information and use your official PampangaStateU institutional email address when requesting access.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Account Responsibilities</h3>
          <ul className="text-sm leading-relaxed mb-4 list-disc pl-5 space-y-1">
            <li>You must provide accurate and truthful information when creating your account</li>
            <li>You must use your own PampangaStateU institutional email address</li>
            <li>You are responsible for maintaining the confidentiality of your account credentials</li>
            <li>You must not share your account with others or allow unauthorized access</li>
          </ul>

          <h3 className="text-base font-semibold mt-6 mb-3">Acceptable Use</h3>
          <p className="text-sm leading-relaxed mb-2">
            When using THESYS+, you agree to:
          </p>
          <ul className="text-sm leading-relaxed mb-4 list-disc pl-5 space-y-1">
            <li>Upload only valid academic documents related to thesis research</li>
            <li>Provide accurate thesis metadata (title, abstract, authors, keywords, etc.)</li>
            <li>Respect intellectual property rights and academic integrity standards</li>
            <li>Use the system for legitimate academic and research purposes only</li>
          </ul>

          <h3 className="text-base font-semibold mt-6 mb-3">Prohibited Activities</h3>
          <p className="text-sm leading-relaxed mb-2">
            You must not:
          </p>
          <ul className="text-sm leading-relaxed mb-4 list-disc pl-5 space-y-1">
            <li>Upload harmful, false, misleading, or unauthorized content</li>
            <li>Upload files unrelated to academic thesis research</li>
            <li>Attempt to circumvent security measures or access restrictions</li>
            <li>Interfere with the proper functioning of the system</li>
            <li>Use the system to violate any applicable laws or regulations</li>
          </ul>

          <h3 className="text-base font-semibold mt-6 mb-3">Thesis Review and Publication</h3>
          <p className="text-sm leading-relaxed mb-4">
            Uploaded theses may require faculty or administrator review before appearing in the repository. THESYS+ reserves the right to reject or remove content that does not meet quality standards or violates these Terms of Use.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">AI-Assisted Features</h3>
          <p className="text-sm leading-relaxed mb-4">
            THESYS+ provides AI-assisted features including semantic search, title similarity validation, and topic trend analysis. These features are decision-support tools and should not be treated as final academic approval or validation. Always consult with your adviser or faculty members for official guidance.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Account Restrictions</h3>
          <p className="text-sm leading-relaxed mb-4">
            Misuse of the system, violation of these Terms of Use, or failure to comply with acceptable use policies may result in rejected access requests, account suspension, or permanent account termination.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Disclaimer</h3>
          <p className="text-sm leading-relaxed mb-4">
            THESYS+ is provided "as is" without warranties of any kind. While we strive to maintain accurate and reliable service, we do not guarantee uninterrupted access or error-free operation.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Changes to Terms</h3>
          <p className="text-sm leading-relaxed mb-4">
            We may update these Terms of Use from time to time. Continued use of THESYS+ after changes are posted constitutes acceptance of the updated terms.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Contact</h3>
          <p className="text-sm leading-relaxed mb-4">
            For questions about these Terms of Use, please contact the THESYS+ administrator at Pampanga State University, College of Computing Studies.
          </p>
        </>
      ),
    };
  }

  if (type === 'help') {
    return {
      title: 'Help Center',
      body: (
        <>
          <p className="text-sm leading-relaxed mb-6">
            Welcome to the THESYS+ Help Center. Find answers to common questions about using the system.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Getting Started</h3>
          
          <h4 className="text-sm font-semibold mt-4 mb-2">How do I request access?</h4>
          <ol className="text-sm leading-relaxed mb-4 list-decimal pl-5 space-y-1">
            <li>Click "Request Access" on the landing page</li>
            <li>Fill in your name, PampangaStateU email, and select your role (Student or Faculty)</li>
            <li>Upload your Student ID or Certificate of Registration (PNG, JPG, or PDF)</li>
            <li>Agree to the Terms and Privacy Policy</li>
            <li>Submit your request</li>
          </ol>

          <h4 className="text-sm font-semibold mt-4 mb-2">How do I verify my email?</h4>
          <p className="text-sm leading-relaxed mb-4">
            After submitting your request, check your PampangaStateU email inbox for a verification link. Click the link to verify your email address. The link expires in 24 hours. If you don't see the email, check your spam folder.
          </p>

          <h4 className="text-sm font-semibold mt-4 mb-2">How do I set my password?</h4>
          <p className="text-sm leading-relaxed mb-4">
            After verifying your email, you will receive a second email with a link to set your password. Click the link and create a secure password for your account.
          </p>

          <h4 className="text-sm font-semibold mt-4 mb-2">How do I sign in?</h4>
          <p className="text-sm leading-relaxed mb-4">
            Once your account is activated, go to the Sign In page and enter your PampangaStateU email and password. Click "Sign In" to access THESYS+.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Using the Repository</h3>

          <h4 className="text-sm font-semibold mt-4 mb-2">How do I search for theses?</h4>
          <p className="text-sm leading-relaxed mb-4">
            Use the search bar on the Repository page to enter keywords, topics, or author names. THESYS+ uses semantic search to find conceptually related theses, not just exact keyword matches.
          </p>

          <h4 className="text-sm font-semibold mt-4 mb-2">What is the similarity threshold?</h4>
          <p className="text-sm leading-relaxed mb-4">
            The similarity threshold controls how strict semantic search results are. A higher threshold (e.g., 0.7) returns only very similar theses, while a lower threshold (e.g., 0.3) returns more loosely related results. Adjust the slider before searching to set your preferred strictness.
          </p>

          <h4 className="text-sm font-semibold mt-4 mb-2">How do I save theses?</h4>
          <p className="text-sm leading-relaxed mb-4">
            Click the bookmark icon on any thesis card to save it to your profile. View your saved theses on your Profile page.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Title Similarity</h3>

          <h4 className="text-sm font-semibold mt-4 mb-2">How do I validate a thesis title?</h4>
          <p className="text-sm leading-relaxed mb-4">
            Go to the Title Similarity page. You can either manually enter a proposed title or upload a document containing your title. Click "Validate Title" to see how similar your title is to existing theses in the repository.
          </p>

          <h4 className="text-sm font-semibold mt-4 mb-2">What do the similarity scores mean?</h4>
          <ul className="text-sm leading-relaxed mb-4 list-disc pl-5 space-y-1">
            <li><strong>High similarity (70%+):</strong> Your title is very similar to existing theses. Consider revising to make it more unique.</li>
            <li><strong>Moderate similarity (40-69%):</strong> Some overlap exists. Review similar theses to ensure your research is distinct.</li>
            <li><strong>Low similarity (below 40%):</strong> Your title appears unique compared to existing theses.</li>
          </ul>

          <h3 className="text-base font-semibold mt-6 mb-3">Uploading Theses</h3>

          <h4 className="text-sm font-semibold mt-4 mb-2">How do I upload a thesis?</h4>
          <ol className="text-sm leading-relaxed mb-4 list-decimal pl-5 space-y-1">
            <li>Go to the Upload Thesis page</li>
            <li>Fill in the thesis metadata (title, abstract, authors, keywords, program, year, adviser)</li>
            <li>Upload your thesis document (PDF or DOCX, max 10 MB)</li>
            <li>Click "Upload Thesis"</li>
          </ol>

          <h4 className="text-sm font-semibold mt-4 mb-2">What happens after I upload?</h4>
          <p className="text-sm leading-relaxed mb-4">
            Your thesis will be reviewed by faculty or administrators before appearing in the repository. You will be notified once your thesis is approved.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Trend Analysis and Analytics</h3>

          <h4 className="text-sm font-semibold mt-4 mb-2">What is Trend Analysis?</h4>
          <p className="text-sm leading-relaxed mb-4">
            Trend Analysis identifies saturated, emerging, and underexplored research topics using TF-IDF and K-Means clustering. Use it to discover research gaps and trending topics in your field.
          </p>

          <h4 className="text-sm font-semibold mt-4 mb-2">What is the Analytics Dashboard?</h4>
          <p className="text-sm leading-relaxed mb-4">
            The Analytics Dashboard provides insights about the repository, including program distribution, thesis counts by year, and historical research growth trends.
          </p>

          <h3 className="text-base font-semibold mt-6 mb-3">Need More Help?</h3>
          <p className="text-sm leading-relaxed mb-4">
            If you have questions not covered in this Help Center, please contact the THESYS+ administrator at Pampanga State University, College of Computing Studies.
          </p>
        </>
      ),
    };
  }

  return { title: 'Information', body: <p>Content not available.</p> };
}
