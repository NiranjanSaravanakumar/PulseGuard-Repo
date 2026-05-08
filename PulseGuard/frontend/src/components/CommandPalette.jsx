/**
 * CommandPalette — Ctrl+K quick-switch for Operator / Engineer / Admin views.
 * Also exposes actions: clear alerts, toggle dark/light (reserved).
 */
import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

const COMMANDS = [
  { id: "operator", label: "Switch to Operator View",  icon: "👷", category: "Role",   action: "setRole" },
  { id: "engineer", label: "Switch to Engineer View",  icon: "⚙️",  category: "Role",   action: "setRole" },
  { id: "admin",    label: "Switch to Admin View",     icon: "🛡",  category: "Role",   action: "setRole" },
];

export default function CommandPalette({ open, onClose, currentRole, onRoleChange }) {
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const execute = (cmd) => {
    if (cmd.action === "setRole") onRoleChange(cmd.id);
    onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="palette-backdrop"
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            key="palette-panel"
            className="fixed top-[20%] left-1/2 -translate-x-1/2 z-50 w-full max-w-lg"
            initial={{ opacity: 0, scale: 0.94, y: -20 }}
            animate={{ opacity: 1, scale: 1,    y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: -10 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <div className="bg-slate-900/95 backdrop-blur-xl rounded-2xl border border-slate-700/60 shadow-2xl shadow-black/50 overflow-hidden">
              {/* Search bar */}
              <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800">
                <span className="text-slate-500 text-sm">⌘</span>
                <input
                  ref={inputRef}
                  readOnly
                  placeholder="Command Palette  —  select an action"
                  className="flex-1 bg-transparent text-sm text-white placeholder-slate-600 outline-none"
                />
                <kbd className="text-[10px] px-1.5 py-0.5 rounded border border-slate-700 text-slate-500 font-mono">ESC</kbd>
              </div>

              {/* Commands */}
              <ul className="py-2">
                {COMMANDS.map((cmd) => {
                  const isActive = cmd.id === currentRole;
                  return (
                    <motion.li
                      key={cmd.id}
                      whileHover={{ backgroundColor: "rgba(99,102,241,0.12)" }}
                      className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                        isActive ? "bg-cyan-500/10" : ""
                      }`}
                      onClick={() => execute(cmd)}
                    >
                      <span className="text-lg w-6 text-center select-none">{cmd.icon}</span>
                      <div className="flex-1">
                        <p className={`text-sm font-medium ${isActive ? "text-cyan-400" : "text-slate-200"}`}>
                          {cmd.label}
                        </p>
                        <p className="text-[10px] text-slate-600 uppercase tracking-widest mt-0.5">{cmd.category}</p>
                      </div>
                      {isActive && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400 font-semibold">
                          ACTIVE
                        </span>
                      )}
                    </motion.li>
                  );
                })}
              </ul>

              {/* Footer hint */}
              <div className="px-4 py-2 border-t border-slate-800 text-[10px] text-slate-600 flex items-center gap-3">
                <span><kbd className="font-mono">↑↓</kbd> navigate</span>
                <span><kbd className="font-mono">↵</kbd> select</span>
                <span><kbd className="font-mono">Ctrl+K</kbd> toggle</span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
