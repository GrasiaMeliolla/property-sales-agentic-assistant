"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MessageCircle, X, Send, Building2, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { createConversation, sendMessageStream, ProjectSummary, StreamChunk } from "@/lib/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  properties?: ProjectSummary[];
  isStreaming?: boolean;
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const initConversation = useCallback(async () => {
    try {
      const conversation = await createConversation();
      setConversationId(conversation.id);
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content:
            "Hello! I'm **Luna**, your property assistant at Silver Land Properties. I'm here to help you find your perfect property. What kind of property are you looking for?",
        },
      ]);
    } catch (err) {
      setError("Failed to connect. Please try again.");
      console.error(err);
    }
  }, []);

  useEffect(() => {
    if (isOpen && !conversationId) {
      initConversation();
    }
  }, [isOpen, conversationId, initConversation]);

  const handleSend = async () => {
    if (!input.trim() || !conversationId || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
    };

    const assistantMessageId = (Date.now() + 1).toString();

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    // Add empty assistant message for streaming
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        isStreaming: true,
      },
    ]);

    try {
      let fullContent = "";
      let properties: ProjectSummary[] = [];

      for await (const chunk of sendMessageStream(conversationId, userMessage.content)) {
        const { type, data } = chunk as StreamChunk;

        if (type === "content") {
          fullContent += data as string;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: fullContent }
                : msg
            )
          );
        } else if (type === "properties") {
          properties = (data as ProjectSummary[]) || [];
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, properties }
                : msg
            )
          );
        } else if (type === "error") {
          setError(data as string);
        }
      }

      // Mark streaming as complete
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, isStreaming: false }
            : msg
        )
      );
    } catch (err) {
      setError("Failed to send message. Please try again.");
      console.error(err);
      // Remove the empty assistant message on error
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantMessageId));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatPrice = (price: number | null) => {
    if (!price) return "Price on request";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(price);
  };

  return (
    <>
      {/* Chat Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 bg-primary-600 hover:bg-primary-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all duration-300 hover:scale-105"
        aria-label="Toggle chat"
      >
        {isOpen ? (
          <X className="w-6 h-6" />
        ) : (
          <MessageCircle className="w-6 h-6" />
        )}
      </button>

      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 z-50 w-96 h-[600px] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-silver-200">
          {/* Header */}
          <div className="bg-gradient-to-r from-primary-700 to-primary-600 text-white px-4 py-3 flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
              <Building2 className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-sm">Luna</h3>
              <p className="text-xs text-white/80">Silver Land Properties</p>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 hover:bg-white/20 rounded transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-silver-50 scrollbar-thin">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] ${
                    message.role === "user"
                      ? "bg-primary-600 text-white rounded-2xl rounded-br-sm"
                      : "bg-white text-silver-800 rounded-2xl rounded-bl-sm shadow-sm border border-silver-100"
                  } px-4 py-2.5`}
                >
                  {message.role === "assistant" ? (
                    <div className="text-sm prose prose-sm prose-silver max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                          ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
                          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2">{children}</ol>,
                          li: ({ children }) => <li className="mb-1">{children}</li>,
                          strong: ({ children }) => <strong className="font-semibold text-primary-700">{children}</strong>,
                          a: ({ href, children }) => (
                            <a href={href} className="text-primary-600 underline" target="_blank" rel="noopener noreferrer">
                              {children}
                            </a>
                          ),
                        }}
                      >
                        {message.content}
                      </ReactMarkdown>
                      {message.isStreaming && message.content && (
                        <span className="inline-block w-2 h-4 bg-primary-500 animate-pulse ml-1" />
                      )}
                    </div>
                  ) : (
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  )}

                  {/* Property Cards */}
                  {message.properties && message.properties.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {message.properties.slice(0, 3).map((prop, idx) => (
                        <div
                          key={prop.id || idx}
                          className="bg-silver-50 rounded-lg p-3 text-silver-700"
                        >
                          <h4 className="font-medium text-sm text-silver-900 line-clamp-1">
                            {prop.project_name}
                          </h4>
                          <div className="mt-1 flex flex-wrap gap-2 text-xs">
                            {prop.city && (
                              <span className="bg-silver-200 px-2 py-0.5 rounded">
                                {prop.city}
                              </span>
                            )}
                            {prop.bedrooms && (
                              <span className="bg-silver-200 px-2 py-0.5 rounded">
                                {prop.bedrooms} bed
                              </span>
                            )}
                            <span className="bg-primary-100 text-primary-700 px-2 py-0.5 rounded font-medium">
                              {formatPrice(prop.price_usd)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
              <div className="flex justify-start">
                <div className="bg-white text-silver-500 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm border border-silver-100">
                  <Loader2 className="w-5 h-5 animate-spin" />
                </div>
              </div>
            )}

            {error && (
              <div className="text-center text-red-500 text-sm py-2">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 bg-white border-t border-silver-200">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your message..."
                className="flex-1 px-4 py-2.5 bg-silver-100 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all"
                disabled={isLoading || !conversationId}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading || !conversationId}
                className="w-10 h-10 bg-primary-600 hover:bg-primary-700 disabled:bg-silver-300 text-white rounded-full flex items-center justify-center transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
