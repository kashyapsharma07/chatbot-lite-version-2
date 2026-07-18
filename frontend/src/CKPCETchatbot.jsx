import { useState, useEffect, useRef, useCallback } from "react";

// ─── Utility: pretty label for a URL ─────────────────────────────────────────
function prettyLabel(url) {
  try {
    const u = new URL(url);
    const host = u.hostname.replace("www.", "");
    if (host.includes("instagram.com")) return "Instagram ↗";
    if (host.includes("facebook.com")) return "Facebook ↗";
    if (host.includes("youtube.com") || host.includes("youtu.be")) {
      if (u.pathname.startsWith("/watch")) return "Watch on YouTube ↗";
      if (u.pathname.startsWith("/@")) return "YouTube Channel ↗";
      return "YouTube ↗";
    }
    if (host.includes("linkedin.com")) return "LinkedIn ↗";
    if (host.includes("goo.gl") || host.includes("maps.google")) return "Google Maps ↗";
    if (host.includes("drive.google.com")) return "View Document ↗";
    if (host.includes("forms.gle") || host.includes("docs.google.com/forms")) return "Open Form ↗";
    if (host.includes("wa.link") || host.includes("whatsapp.com")) return "WhatsApp ↗";
    if (host.includes("ckpcmc.org")) {
      // Show the path for ckpcmc links
      const path = u.pathname.replace(/\/$/, "");
      if (path && path !== "/") return "ckpcmc.org" + path + " ↗";
      return "ckpcmc.org ↗";
    }
    if (host.includes("grayquest.com")) return "Pay Fees Online ↗";
    if (host.includes("acpc.gujarat.gov.in")) return "ACPC Portal ↗";
    if (host.includes("gtu.ac.in")) return "GTU Portal ↗";
    if (host.includes("nirfindia.org")) return "NIRF Portal ↗";
    return host + " ↗";
  } catch {
    return url.length > 35 ? url.slice(0, 32) + "…" : url;
  }
}

// ─── Utility: prepare text for natural TTS pronunciation ──────────────────────
function prepareTextForSpeech(text) {
  if (!text) return "";

  // 1. Replace Rupee symbols with spoken words
  let clean = text.replace(/₹\s*(\d+(?:,\d+)*)/g, "$1 Rupees");
  clean = clean.replace(/\bRs\.\s*(\d+(?:,\d+)*)/gi, "$1 Rupees");
  clean = clean.replace(/\bRs\s*(\d+(?:,\d+)*)/gi, "$1 Rupees");

  // 2. Remove URLs
  clean = clean.replace(/(https?:\/\/[^\s]+)/g, "");

  // 3. Expand contractions & abbreviations for perfect pronunciation
  clean = clean
    .replace(/\bCKPCET\b/gi, "C K P C E T")
    .replace(/\bCKPCMC\b/gi, "C K P C M C")
    .replace(/\bCKP\b/gi, "C K P")
    .replace(/\bI'm\b/gi, "I am")
    .replace(/\bI’m\b/gi, "I am")
    .replace(/\bwhat's\b/gi, "what is")
    .replace(/\bwhat’s\b/gi, "what is")
    .replace(/\bit's\b/gi, "it is")
    .replace(/\bit’s\b/gi, "it is")
    .replace(/\blet's\b/gi, "let us")
    .replace(/\blet’s\b/gi, "let us")
    .replace(/\bwe'll\b/gi, "we will")
    .replace(/\bwe’ll\b/gi, "we will")
    .replace(/\byou're\b/gi, "you are")
    .replace(/\byou’re\b/gi, "you are")
    .replace(/\bthey're\b/gi, "they are")
    .replace(/\bthey’re\b/gi, "they are")
    .replace(/\bdon't\b/gi, "do not")
    .replace(/\bdon’t\b/gi, "do not")
    .replace(/\bcan't\b/gi, "cannot")
    .replace(/\bcan’t\b/gi, "cannot")
    .replace(/\bwon't\b/gi, "will not")
    .replace(/\bwon’t\b/gi, "will not")
    .replace(/\bshouldn't\b/gi, "should not")
    .replace(/\bshouldn’t\b/gi, "should not");

  // 4. Remove all emojis & special unicode symbols
  clean = clean.replace(/[\u2700-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDD10-\uDDFF]/g, "");

  // 5. Remove standard markdown and structural characters
  clean = clean.replace(/[*#_~`>•\-–—\[\]\(\)]/g, "");

  // 6. Replace multiple consecutive spaces with a single space, but preserve newlines
  clean = clean.replace(/[^\S\r\n]+/g, " ");

  return clean.trim();
}

// ─── Utility: Split text into spoken sentences, protecting abbreviations and decimals ───
function splitIntoSentences(text) {
  if (!text) return [];

  // Split by newlines first to handle bullet points and paragraphs separately
  const lines = text.split(/[\r\n]+/);
  const allSentences = [];

  for (let line of lines) {
    line = line.trim();
    if (!line) continue;

    // Clean up bullet points at the start of the line (e.g. "• Item", "- Item" -> "Item")
    let cleanedLine = line.replace(/^[\s•\-\*]+\s*/, "");
    if (!cleanedLine) continue;

    // 1. Temporarily protect decimal numbers (e.g., 8.5 -> 8__DECIMAL__5)
    let processed = cleanedLine.replace(/(\d+)\.(\d+)/g, "$1__DECIMAL__$2");

    // 2. Temporarily protect common abbreviations (case-insensitive)
    processed = processed
      .replace(/\bDr\./gi, "Dr__DOT__")
      .replace(/\bMr\./gi, "Mr__DOT__")
      .replace(/\bMrs\./gi, "Mrs__DOT__")
      .replace(/\bMs\./gi, "Ms__DOT__")
      .replace(/\bProf\./gi, "Prof__DOT__")
      .replace(/\bB\.E\./gi, "B__DOT__E__DOT__")
      .replace(/\bM\.E\./gi, "M__DOT__E__DOT__")
      .replace(/\bPh\.D\./gi, "Ph__DOT__D__DOT__")
      .replace(/\bPh\.D\b/gi, "Ph__DOT__D")
      .replace(/\bB\.E\b/gi, "B__DOT__E")
      .replace(/\bM\.E\b/gi, "M__DOT__E")
      .replace(/\bB\.Com\./gi, "B__DOT__Com__DOT__")
      .replace(/\bB\.Com\b/gi, "B__DOT__Com")
      .replace(/\bB\.B\.A\./gi, "B__DOT__B__DOT__A__DOT__")
      .replace(/\bB\.C\.A\./gi, "B__DOT__C__DOT__A__DOT__")
      .replace(/\bV\.N\.S\.G\.U\./gi, "V__DOT__N__DOT__S__DOT__G__DOT__U__DOT__")
      .replace(/\bA\.C\.P\.C\./gi, "A__DOT__C__DOT__P__DOT__C__DOT__")
      .replace(/\ba\.m\./gi, "a__DOT__m__DOT__")
      .replace(/\bp\.m\./gi, "p__DOT__m__DOT__")
      .replace(/\be\.g\./gi, "e__DOT__g__DOT__")
      .replace(/\bi\.e\./gi, "i__DOT__e__DOT__")
      .replace(/\bvs\./gi, "vs__DOT__");

    // 3. Split by sentence-ending punctuation (., ?, !)
    // We removed colons (:) from here so numbers and lists read as single cohesive sentences.
    const rawParts = processed.split(/([.?!])(?:\s+|$)/);

    for (let i = 0; i < rawParts.length; i += 2) {
      let sentence = rawParts[i];
      let punct = rawParts[i + 1] || "";
      if (sentence) {
        let combined = (sentence + punct).trim();
        if (combined) {
          // Restore the protected decimals and abbreviations
          let restored = combined
            .replace(/__DECIMAL__/g, ".")
            .replace(/__DOT__/g, ".")
            .replace(/\s+/g, " ") // Clean up multiple consecutive spaces
            .trim();
          if (restored) {
            allSentences.push(restored);
          }
        }
      }
    }
  }

  return allSentences;
}

// ─── Utility: Speech Queue Manager for smooth, natural sentence-by-sentence TTS ───
class SpeechQueueManager {
  constructor() {
    this.queue = [];
    this.currentIndex = -1;
    this.isPlaying = false;
    this.currentUtterance = null;
    this.timer = null;
  }

  // Preprocesses response, splits into sentences, and queues them for speech
  speak(text) {
    this.cancel(); // Cancel any ongoing speech first

    if (!text) return;

    // 1. Preprocess the response for TTS pronunciation
    const cleanText = prepareTextForSpeech(text);
    
    // 2. Split response into individual sentences
    this.queue = splitIntoSentences(cleanText);
    this.currentIndex = 0;
    this.isPlaying = true;

    // 3. Prevent Chrome's speech synthesis engine block by running speak after a small timeout
    this.timer = setTimeout(() => {
      this.speakNext();
    }, 50);
  }

  // Speaks the next sentence in the queue sequentially
  speakNext() {
    if (!this.isPlaying) return;

    // Queue finished
    if (this.currentIndex >= this.queue.length) {
      this.isPlaying = false;
      this.currentUtterance = null;
      return;
    }

    const sentence = this.queue[this.currentIndex];
    
    // Create separate SpeechSynthesisUtterance for each sentence
    const utterance = new SpeechSynthesisUtterance(sentence);
    this.currentUtterance = utterance;

    // Use onend callback to automatically speak the next sentence with a natural pause
    utterance.onend = () => {
      if (this.currentUtterance === utterance) {
        this.currentIndex++;
        // Add a natural 150ms pause between sentences
        this.timer = setTimeout(() => {
          this.speakNext();
        }, 150);
      }
    };

    // Skip to the next sentence if an error occurs to prevent getting stuck
    utterance.onerror = (e) => {
      if (e.error !== "interrupted") {
        console.error("SpeechSynthesis error:", e);
        if (this.currentUtterance === utterance) {
          this.currentIndex++;
          this.speakNext();
        }
      }
    };

    // Play the utterance
    window.speechSynthesis.speak(utterance);
  }

  // Immediately cancels speech, clears timers, and resets queue state
  cancel() {
    this.isPlaying = false;
    this.queue = [];
    this.currentIndex = -1;
    this.currentUtterance = null;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    window.speechSynthesis.cancel();
  }
}

// ─── Utility: linkify text + render newlines ─────────────────────────────────
function Linkified({ text }) {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const parts = text.split(urlRegex);
  return (
    <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {parts.map((part, i) =>
        urlRegex.test(part) ? (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "#1a73e8",
              textDecoration: "none",
              borderBottom: "1px solid rgba(26,115,232,0.3)",
              fontWeight: 500,
            }}
          >
            {prettyLabel(part)}
          </a>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </span>
  );
}

// ─── Loading Dots ────────────────────────────────────────────────────────────
function LoadingDots() {
  const [dots, setDots] = useState(1);
  useEffect(() => {
    const t = setInterval(() => setDots((d) => (d % 3) + 1), 500);
    return () => clearInterval(t);
  }, []);
  return (
    <div style={styles.botBubble}>
      <span style={styles.loadingSpinner} />
      <span style={{ fontStyle: "italic", color: "#888" }}>
        ⏳ Please wait{".".repeat(dots)}
      </span>
    </div>
  );
}

// ─── Message Bubble ──────────────────────────────────────────────────────────
function MessageBubble({ msg, onSuggestionClick }) {
  const isUser = msg.role === "user";
  const hasContent = msg.content && msg.content.trim() !== "";
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        animation: "msgIn 0.25s ease",
      }}
    >
      {(isUser || hasContent) && (
        <div style={isUser ? styles.userBubble : styles.botBubble}>
          {isUser ? (
            <span>{msg.content}</span>
          ) : (
            <Linkified text={msg.content} />
          )}
        </div>
      )}
      {/* Suggestion chips below bot messages */}
      {!isUser && msg.suggestions?.length > 0 && (
        <div style={styles.suggestionsRow}>
          {msg.suggestions.map((s, i) => (
            <button
              key={i}
              style={styles.suggestionChip}
              onClick={() => onSuggestionClick?.(s)}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(218,16,57,0.12)";
                e.currentTarget.style.borderColor = "#da1039";
                e.currentTarget.style.color = "#da1039";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(218,16,57,0.05)";
                e.currentTarget.style.borderColor = "rgba(218,16,57,0.2)";
                e.currentTarget.style.color = "#444";
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── FAQ Chip ────────────────────────────────────────────────────────────────
function FAQChip({ faq, onSelect }) {
  return (
    <button
      onClick={() => onSelect(faq.question)}
      style={styles.faqChip}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "rgba(218,16,57,0.12)";
        e.currentTarget.style.borderColor = "#da1039";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "rgba(218,16,57,0.04)";
        e.currentTarget.style.borderColor = "rgba(218,16,57,0.2)";
      }}
    >
      <span style={styles.faqChipLabel}>{faq.stream}</span>
      <span style={styles.faqChipQ}>{faq.question}</span>
      <span style={styles.faqChipP}>{faq.preview}</span>
    </button>
  );
}

// ─── Main App ────────────────────────────────────────────────────────────────
export default function App() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [faqs, setFaqs] = useState([]);
  const [showFAQs, setShowFAQs] = useState(false);
  const [isTtsEnabled, setIsTtsEnabled] = useState(() => {
    return localStorage.getItem("isTtsEnabled") === "true";
  });
  const isTtsEnabledRef = useRef(isTtsEnabled);
  useEffect(() => {
    isTtsEnabledRef.current = isTtsEnabled;
  }, [isTtsEnabled]);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const speechManagerRef = useRef(null);

  // Initialize and clean up Speech Queue Manager
  useEffect(() => {
    speechManagerRef.current = new SpeechQueueManager();
    return () => {
      speechManagerRef.current?.cancel();
    };
  }, []);



  // Auto scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Load FAQs once
  useEffect(() => {
    fetch("/get_faqs")
      .then((r) => r.json())
      .then((d) => setFaqs(d.faqs || []))
      .catch(() => { });
  }, []);

  // Focus input when chat opens
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 200);
  }, [open]);

  // Toggle TTS
  const toggleTts = () => {
    setIsTtsEnabled((prev) => {
      const next = !prev;
      localStorage.setItem("isTtsEnabled", String(next));
      if (!next) {
        speechManagerRef.current?.cancel();
      } else {
        // Unlock SpeechSynthesis on mobile immediately inside user click thread
        const unlock = new SpeechSynthesisUtterance("");
        unlock.volume = 0;
        window.speechSynthesis.speak(unlock);
      }
      return next;
    });
  };

  // ── Send message ──────────────────────────────────────────────────────────
  const sendMessage = useCallback(
    async (overrideText, forceTts = false) => {
      const text = (overrideText ?? input).trim();
      if (!text || loading) return;

      setInput("");
      setShowFAQs(false);
      speechManagerRef.current?.cancel(); // stop any ongoing speech

      // Unlock SpeechSynthesis on mobile immediately inside user interaction event thread
      if (isTtsEnabledRef.current) {
        const unlock = new SpeechSynthesisUtterance("");
        unlock.volume = 0;
        window.speechSynthesis.speak(unlock);
      }

      // Stop voice listening if active
      if (recognitionRef.current && isListening) {
        recognitionRef.current.stop();
      }

      // Add user message and an empty bot message structure to state
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "bot", content: "", suggestions: [] }
      ]);
      setLoading(true);

      try {
        const res = await fetch("/api", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            session_id: sessionId,
          }),
        });

        if (!res.ok) {
          throw new Error("HTTP error connecting to chatbot api");
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let accumulatedContent = "";
        let suggestions = [];

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop();

          for (const line of lines) {
            const cleanLine = line.trim();
            if (cleanLine.startsWith("data: ")) {
              try {
                const event = JSON.parse(cleanLine.slice(6));
                if (event.type === "suggestions") {
                  suggestions = event.suggestions || [];
                  setMessages((prev) => {
                    const next = [...prev];
                    if (next.length > 0) {
                      next[next.length - 1] = {
                        ...next[next.length - 1],
                        suggestions: suggestions,
                      };
                    }
                    return next;
                  });
                } else if (event.type === "content") {
                  accumulatedContent += event.content;
                  setMessages((prev) => {
                    const next = [...prev];
                    if (next.length > 0) {
                      next[next.length - 1] = {
                        ...next[next.length - 1],
                        content: accumulatedContent,
                      };
                    }
                    return next;
                  });
                } else if (event.type === "clear") {
                  accumulatedContent = "";
                  setMessages((prev) => {
                    const next = [...prev];
                    if (next.length > 0) {
                      next[next.length - 1] = {
                        ...next[next.length - 1],
                        content: accumulatedContent,
                      };
                    }
                    return next;
                  });
                }
              } catch (err) {
                console.error("SSE parse error", err);
              }
            }
          }
        }

        // Trigger TTS if enabled
        if (isTtsEnabledRef.current) {
          speechManagerRef.current?.speak(accumulatedContent);
        }

      } catch {
        setMessages((prev) => {
          const next = [...prev];
          if (next.length > 0 && next[next.length - 1].role === "bot" && next[next.length - 1].content === "") {
            next[next.length - 1] = {
              role: "bot",
              content: "❌ Error connecting. Please check if Flask is running.",
              suggestions: [],
            };
          }
          return next;
        });
      } finally {
        setLoading(false);
      }
    },
    [input, loading, sessionId, isTtsEnabled]
  );

  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);
  const sendMessageRef = useRef(null);

  useEffect(() => {
    sendMessageRef.current = sendMessage;
  }, [sendMessage]);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = false;
      rec.lang = "en-US";
      rec.interimResults = false;

      rec.onstart = () => {
        setIsListening(true);
      };

      rec.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          sendMessageRef.current(transcript, isTtsEnabledRef.current);
        }
      };

      rec.onerror = (e) => {
        console.error("Speech recognition error", e);
        setIsListening(false);
      };

      rec.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = rec;
    }
  }, []);

  const toggleListening = () => {
    if (!recognitionRef.current) {
      alert("Speech recognition is not supported in this browser. Please try using Google Chrome or Safari.");
      return;
    }
    if (isListening) {
      recognitionRef.current.stop();
    } else {
      speechManagerRef.current?.cancel();
      // Unlock SpeechSynthesis on mobile immediately inside user click thread
      const unlock = new SpeechSynthesisUtterance("");
      unlock.volume = 0;
      window.speechSynthesis.speak(unlock);
      recognitionRef.current.start();
    }
  };

  // ── Clear history ─────────────────────────────────────────────────────────
  const clearChat = () => {
    speechManagerRef.current?.cancel();
    setMessages([]);
    fetch("/clear_history", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    }).catch(() => { });
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{globalCSS}</style>

      {/* ── Hero Banner ─────────────────────────────────────────── */}
      <div style={styles.page}>
        <nav style={styles.nav}>
          <div style={styles.navBrand}>CKPCMC</div>
          <div style={styles.navLinks}>
            <a href="https://ckpcmc.org" style={styles.navLink}>Home</a>
            <a href="https://ckpcmc.org/event" style={styles.navLink}>Events</a>
            <a href="https://ckpcmc.org/pages-10" style={styles.navLink}>About</a>
            <a href="https://ckpcmc.org/contact" style={styles.navLink}>Contact</a>
          </div>
        </nav>

        <main style={styles.hero}>
          <div style={styles.heroInner}>
            <div style={styles.heroBadge}>Excellence in Commerce & Management</div>
            <h1 style={styles.heroTitle}>
              C. K. Pithawalla College of<br />
              <span style={styles.heroAccent}>Commerce, Management & Computer Application</span>
            </h1>
            <p style={styles.heroSub}>
              Your intelligent assistant for admissions, fees, courses,
              and student activities — available 24 × 7.
            </p>
            <button className="hero-cta" style={styles.heroCTA} onClick={() => setOpen(true)}>
              💬 Chat with CKPCMC Bot
            </button>
          </div>
          <div className="hero-card" style={styles.heroCard}>
            <div style={styles.cardStat}><span style={styles.cardNum}>3 UG</span><span style={styles.cardLbl}>Programs</span></div>
            <div className="card-divider" style={styles.cardDivider} />
            <div style={styles.cardStat}><span style={styles.cardNum}>8 AM - 2 PM</span><span style={styles.cardLbl}>Timings</span></div>
            <div className="card-divider" style={styles.cardDivider} />
            <div style={styles.cardStat}><span style={styles.cardNum}>VNSGU</span><span style={styles.cardLbl}>Affiliated</span></div>
          </div>
        </main>

        {/* FAQ chips on main page */}
        {faqs.length > 0 && (
          <section style={styles.faqSection}>
            <h2 style={styles.faqHeading}>Common Questions</h2>
            <div style={styles.faqGrid}>
              {faqs.map((f, i) => (
                <FAQChip key={i} faq={f} onSelect={(q) => { setOpen(true); setTimeout(() => sendMessage(q), 300); }} />
              ))}
            </div>
          </section>
        )}

        <footer style={styles.footer}>© 2026 CKPCMC Chatbot</footer>
      </div>

      {/* ── Floating Toggle ──────────────────────────────────────── */}
      <button
        className={`chat-fab ${open ? "open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-label="Toggle chat"
      >
        {open ? "✖" : "💬"}
      </button>

      {/* ── Chat Widget ──────────────────────────────────────────── */}
      <div className={`chat-widget ${open ? "open" : ""}`} aria-hidden={!open}>

        {/* Header */}
        <div style={styles.widgetHeader}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={styles.avatar}>🤖</div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>CKPCMC Assistant</div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button
              style={styles.voiceToggleBtn}
              onClick={toggleTts}
              title={isTtsEnabled ? "Disable Text-to-Speech" : "Enable Text-to-Speech"}
            >
              {isTtsEnabled ? "🔊" : "🔇"}
            </button>
            <button style={styles.clearBtn} onClick={clearChat} title="Clear chat">Clear</button>
            <button style={styles.closeBtn} onClick={() => setOpen(false)}>✖</button>
          </div>
        </div>

        {/* Messages */}
        <div style={styles.messages}>
          {messages.length === 0 && (
            <div style={styles.emptyState}>
              <div style={styles.emptyIcon}>🎓</div>
              <p style={{ fontWeight: 600, margin: "8px 0 4px" }}>Welcome to CKPCMC Bot!</p>
              <p style={{ fontSize: 13, color: "#888", lineHeight: 1.5 }}>
                Ask me about admissions, course fees, intake capacity, principal, or timings.
              </p>
              {faqs.length > 0 && (
                <button style={styles.faqToggle} onClick={() => setShowFAQs((s) => !s)}>
                  {showFAQs ? "Hide suggestions ▲" : "Show quick questions ▼"}
                </button>
              )}
              {showFAQs && (
                <div style={styles.inlineFAQs}>
                  {faqs.map((f, i) => (
                    <button
                      key={i}
                      style={styles.inlineFAQ}
                      onClick={() => sendMessage(f.question)}
                    >
                      {f.question}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {messages.map((m, i) => (
            <MessageBubble key={i} msg={m} onSuggestionClick={sendMessage} />
          ))}

          {loading && <LoadingDots />}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div style={styles.inputRow}>
          <input
            ref={inputRef}
            className="chat-input"
            style={styles.inputField}
            value={input}
            placeholder="Ask about B.Com, BBA, BCA…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), sendMessage())}
          />
          <button
            style={{
              ...styles.iconBtn,
              background: isListening ? "linear-gradient(135deg, #c00, #900)" : "rgba(218,16,57,0.08)",
              color: isListening ? "white" : "#da1039",
              animation: isListening ? "pulse 1.5s infinite" : "none",
              opacity: loading ? 0.5 : 1
            }}
            onClick={toggleListening}
            disabled={loading}
            title={isListening ? "Listening... Click to stop" : "Ask by speaking"}
          >
            {isListening ? "🛑" : "🎤"}
          </button>
          <button
            style={{ ...styles.iconBtn, opacity: !input.trim() || loading ? 0.5 : 1 }}
            onClick={() => sendMessage()}
            disabled={!input.trim() || loading}
            title="Send"
          >
            ➤
          </button>
        </div>
      </div>
    </>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────
const BLUE = "#da1039"; // Crimson Red
const BLUE_DARK = "#6d061a"; // Dark Maroon

const styles = {
  // Page
  page: { minHeight: "100vh", background: "#f4f6fb", fontFamily: "'Segoe UI', sans-serif", display: "flex", flexDirection: "column" },

  // Nav
  nav: { background: BLUE_DARK, color: "white", padding: "14px 32px", display: "flex", justifyContent: "space-between", alignItems: "center", position: "sticky", top: 0, zIndex: 100 },
  navBrand: { fontSize: 22, fontWeight: 800, letterSpacing: 1 },
  navLinks: { display: "flex", gap: 24 },
  navLink: { color: "rgba(255,255,255,0.85)", textDecoration: "none", fontSize: 14, fontWeight: 500 },

  // Hero
  hero: { background: `linear-gradient(135deg, ${BLUE_DARK}, ${BLUE})`, color: "white", padding: "64px 32px", display: "flex", flexWrap: "wrap", gap: 40, alignItems: "center", justifyContent: "center" },
  heroInner: { maxWidth: 560 },
  heroBadge: { background: "rgba(255,255,255,0.15)", display: "inline-block", padding: "6px 14px", borderRadius: 20, fontSize: 12, letterSpacing: 1, marginBottom: 18 },
  heroTitle: { fontSize: "clamp(26px, 4vw, 42px)", fontWeight: 800, lineHeight: 1.2, margin: "0 0 16px" },
  heroAccent: { color: "#76c7df" },
  heroSub: { fontSize: 16, opacity: 0.85, lineHeight: 1.7, margin: "0 0 28px" },
  heroCTA: { background: "white", color: BLUE, border: "none", padding: "14px 28px", borderRadius: 30, fontSize: 15, fontWeight: 700, cursor: "pointer", boxShadow: "0 6px 20px rgba(0,0,0,0.25)", transition: "transform 0.2s" },

  heroCard: { background: "rgba(255,255,255,0.1)", backdropFilter: "blur(12px)", border: "1px solid rgba(255,255,255,0.2)", borderRadius: 20, padding: "28px 36px", display: "flex", gap: 24, alignItems: "center" },
  cardStat: { display: "flex", flexDirection: "column", alignItems: "center", gap: 4 },
  cardNum: { fontSize: 28, fontWeight: 800 },
  cardLbl: { fontSize: 12, opacity: 0.8, textAlign: "center" },
  cardDivider: { width: 1, height: 48, background: "rgba(255,255,255,0.25)" },

  // FAQs (main page)
  faqSection: { maxWidth: 960, margin: "48px auto", padding: "0 24px", width: "100%" },
  faqHeading: { fontSize: 22, fontWeight: 700, color: BLUE_DARK, marginBottom: 20 },
  faqGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 },
  faqChip: { textAlign: "left", background: "rgba(218,16,57,0.04)", border: "1px solid rgba(218,16,57,0.2)", borderRadius: 12, padding: "14px 16px", cursor: "pointer", transition: "all 0.2s", display: "flex", flexDirection: "column", gap: 4 },
  faqChipLabel: { fontSize: 10, fontWeight: 700, color: BLUE, textTransform: "uppercase", letterSpacing: 0.5 },
  faqChipQ: { fontSize: 13, fontWeight: 600, color: "#222" },
  faqChipP: { fontSize: 12, color: "#777", lineHeight: 1.4 },

  // Footer
  footer: { textAlign: "center", padding: "20px", color: "#888", fontSize: 13, marginTop: "auto" },

  // FAB and Widget are styled via globalCSS for mobile responsiveness and performance

  // Widget Header
  widgetHeader: { background: `linear-gradient(135deg, ${BLUE}, ${BLUE_DARK})`, color: "white", padding: "14px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" },
  avatar: { width: 34, height: 34, background: "rgba(255,255,255,0.15)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 },

  clearBtn: { background: "rgba(255,255,255,0.12)", color: "white", border: "1px solid rgba(255,255,255,0.2)", padding: "4px 10px", borderRadius: 8, fontSize: 12, cursor: "pointer" },
  closeBtn: { background: "none", border: "none", color: "white", fontSize: 16, cursor: "pointer", padding: "2px 6px" },
  voiceToggleBtn: { background: "none", border: "none", color: "white", fontSize: 16, cursor: "pointer", padding: "2px 4px", opacity: 0.8 },

  // Messages
  messages: { flex: 1, overflowY: "auto", padding: "14px", display: "flex", flexDirection: "column", gap: 8, background: "linear-gradient(to bottom, #f9f9f9, #f1f1f1)" },

  // Bubbles
  userBubble: { background: `linear-gradient(135deg, ${BLUE}, ${BLUE_DARK})`, color: "white", padding: "10px 14px", borderRadius: "18px 18px 4px 18px", maxWidth: "75%", fontSize: 14, boxShadow: "0 3px 8px rgba(0,0,0,0.15)", lineHeight: 1.5 },
  botBubble: { background: "white", color: "#333", padding: "10px 14px", borderRadius: "18px 18px 18px 4px", maxWidth: "75%", fontSize: 14, boxShadow: "0 3px 8px rgba(0,0,0,0.1)", lineHeight: 1.5, display: "flex", alignItems: "center", gap: 8 },

  // Loading
  loadingSpinner: { width: 10, height: 10, borderRadius: "50%", background: `linear-gradient(90deg, ${BLUE}, #4fc3f7)`, display: "inline-block", animation: "pulse 1s infinite ease-in-out", flexShrink: 0 },

  // Empty state
  emptyState: { textAlign: "center", padding: "24px 12px", color: "#555" },
  emptyIcon: { fontSize: 40, marginBottom: 8 },
  faqToggle: { marginTop: 14, background: "none", border: `1px solid ${BLUE}`, color: BLUE, padding: "6px 14px", borderRadius: 20, fontSize: 12, cursor: "pointer" },
  inlineFAQs: { display: "flex", flexDirection: "column", gap: 8, marginTop: 12, textAlign: "left" },
  inlineFAQ: { background: "white", border: "1px solid #dde", padding: "8px 12px", borderRadius: 10, fontSize: 13, textAlign: "left", cursor: "pointer", color: "#333" },

  // Input
  inputRow: { display: "flex", gap: 8, padding: "12px 14px", borderTop: "1px solid #eee", background: "white", alignItems: "center" },
  langSelect: { padding: "8px 4px", borderRadius: 16, border: "none", fontSize: 13, fontWeight: "600", background: "rgba(218,16,57,0.08)", color: BLUE, cursor: "pointer", outline: "none" },
  inputField: { flex: 1, border: "none", outline: "none", fontSize: 14, background: "rgba(0,0,0,0.04)", padding: "10px 14px", borderRadius: 16 },
  iconBtn: { width: 38, height: 38, borderRadius: "50%", background: `linear-gradient(135deg, ${BLUE}, ${BLUE_DARK})`, border: "none", color: "white", fontSize: 14, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "transform 0.2s" },
  iconBtnListening: { background: "linear-gradient(135deg, #c00, #900)", animation: "pulse 1.5s infinite" },

  // Follow-up suggestions
  suggestionsRow: { display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6, maxWidth: "85%" },
  suggestionChip: { background: "rgba(218,16,57,0.05)", border: "1px solid rgba(218,16,57,0.2)", borderRadius: 16, padding: "5px 12px", fontSize: 12, color: "#444", cursor: "pointer", transition: "all 0.2s", fontFamily: "inherit", lineHeight: 1.4 },
};

const globalCSS = `
  @keyframes msgIn {
    from { opacity: 0; transform: translateY(10px) scale(0.95); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes pulse {
    0%,100% { transform: scale(1); }
    50%      { transform: scale(1.15); }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #f4f6fb; }
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); border-radius: 10px; }

  /* Floating Action Button (FAB) */
  .chat-fab {
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, #da1039, #6d061a);
    color: white;
    font-size: 24px;
    border: none;
    cursor: pointer;
    z-index: 9999;
    box-shadow: 0 8px 32px rgba(218, 16, 57, 0.3);
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    display: flex;
    align-items: center;
    justify-content: center;
    outline: none;
  }
  .chat-fab:hover {
    transform: scale(1.1) rotate(5deg);
    box-shadow: 0 10px 40px rgba(218, 16, 57, 0.45);
  }
  .chat-fab:active {
    transform: scale(0.95);
  }
  .chat-fab.open {
    background: #333;
    transform: rotate(90deg);
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
  }

  /* Chat Widget Container */
  .chat-widget {
    position: fixed;
    bottom: 100px;
    right: 24px;
    width: 380px;
    height: 600px;
    max-height: calc(100vh - 140px);
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 24px;
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.18);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 9998;
    opacity: 0;
    transform: scale(0.1);
    transform-origin: bottom right;
    pointer-events: none;
    transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.3s ease;
  }
  .chat-widget.open {
    opacity: 1;
    transform: scale(1);
    pointer-events: auto;
  }

  /* Input fields focusing */
  .chat-input {
    transition: all 0.2s ease;
    border: 1px solid transparent !important;
  }
  .chat-input:focus {
    background: white !important;
    border-color: rgba(218, 16, 57, 0.3) !important;
    box-shadow: 0 0 0 3px rgba(218, 16, 57, 0.1) !important;
  }

  /* Hero button hover scale */
  .hero-cta {
    transition: all 0.2s ease;
  }
  .hero-cta:hover {
    transform: translateY(-2px) scale(1.05);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3) !important;
  }
  .hero-cta:active {
    transform: translateY(0) scale(0.98);
  }

  /* Responsive styling for hero card stats */
  @media (max-width: 600px) {
    .hero-card {
      flex-direction: column !important;
      gap: 16px !important;
      padding: 20px 24px !important;
      width: 100% !important;
    }
    .card-divider {
      width: 100% !important;
      height: 1px !important;
      background: rgba(255, 255, 255, 0.15) !important;
    }
  }

  /* Responsive mobile adjustments for chat widget */
  @media (max-width: 480px) {
    .chat-widget {
      bottom: 0 !important;
      right: 0 !important;
      width: 100% !important;
      height: 100% !important;
      max-height: 100% !important;
      border-radius: 0 !important;
      border: none !important;
      z-index: 10000 !important;
      transform-origin: bottom right;
    }
    .chat-widget.open {
      transform: scale(1) !important;
    }
  }
`;