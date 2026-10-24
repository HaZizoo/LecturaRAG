import { useEffect, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { FlashcardsPanel } from "./components/FlashcardsPanel";
import { QuizPanel } from "./components/QuizPanel";
import { Sidebar } from "./components/Sidebar";
import { WorkspaceEmpty } from "./components/WorkspaceEmpty";
import { WorkspaceHeader } from "./components/WorkspaceHeader";
import { useChat } from "./hooks/useChat";
import { useDocuments } from "./hooks/useDocuments";
import { useFlashcards } from "./hooks/useFlashcards";
import { useHealth } from "./hooks/useHealth";
import { useQuiz } from "./hooks/useQuiz";
import type { DocumentSummary, TabId } from "./lib/types";

const TABS: TabId[] = ["chat", "flashcards", "quiz"];

export default function App() {
  const documents = useDocuments();
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const selected = documents.selectedDocument;
  const documentId = selected?.id ?? null;
  const chat = useChat(documentId);
  const flashcards = useFlashcards(documentId);
  const quiz = useQuiz(documentId);
  const { health, isOnline } = useHealth();

  useEffect(() => {
    window.document.title = selected
      ? `${selected.title} · LecturaRAG`
      : "LecturaRAG · AI Study Workspace";
  }, [selected]);

  useEffect(() => {
    if (!sidebarOpen) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [sidebarOpen]);

  const selectDocument = (id: string) => {
    documents.selectDocument(id);
    setSidebarOpen(false);
  };

  const upload = async (file: File) => {
    const uploaded = await documents.upload(file);
    if (uploaded) setSidebarOpen(false);
    return uploaded;
  };

  const removeDocument = async (document: DocumentSummary) => {
    const confirmed = window.confirm(
      `Delete "${document.title}"? Its chat history, flashcard decks, and quizzes will also be removed.`,
    );
    if (!confirmed) return;
    await documents.remove(document.id);
  };

  return (
    <div className="min-h-dvh">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        documents={documents.documents}
        selectedId={documentId}
        isLoading={documents.isLoading}
        error={documents.error}
        uploading={documents.uploading}
        uploadError={documents.uploadError}
        deletingId={documents.deletingId}
        health={health}
        isOnline={isOnline}
        onSelect={selectDocument}
        onUpload={upload}
        onClearUploadError={documents.clearUploadError}
        onDelete={(document) => void removeDocument(document)}
        onRefresh={() => void documents.refresh()}
      />

      {sidebarOpen ? (
        <button
          type="button"
          aria-label="Close lecture library"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/65 backdrop-blur-sm lg:hidden"
        />
      ) : null}

      <div className="flex h-dvh flex-col lg:pl-80">
        <WorkspaceHeader
          document={selected}
          activeTab={activeTab}
          isSidebarOpen={sidebarOpen}
          onTabChange={setActiveTab}
          onOpenSidebar={() => setSidebarOpen(true)}
        />

        <main className="min-h-0 flex-1">
          {!selected ? (
            <WorkspaceEmpty
              isLoading={documents.isLoading}
              listError={documents.error}
              uploading={documents.uploading}
              uploadError={documents.uploadError}
              onUpload={upload}
              onClearUploadError={documents.clearUploadError}
              onRetry={() => void documents.refresh()}
            />
          ) : (
            <>
              {TABS.map((tab) => (
                <div
                  key={tab}
                  id={`panel-${tab}`}
                  role="tabpanel"
                  aria-labelledby={`tab-${tab}`}
                  hidden={activeTab !== tab}
                  className="h-full"
                >
                  {tab === "chat" ? (
                    <ChatPanel
                      document={selected}
                      messages={chat.messages}
                      isLoadingHistory={chat.isLoadingHistory}
                      isSending={chat.isSending}
                      error={chat.error}
                      onSend={chat.send}
                      onRetry={chat.reloadHistory}
                    />
                  ) : null}

                  {tab === "flashcards" ? (
                    <FlashcardsPanel
                      document={selected}
                      deck={flashcards.deck}
                      isLoading={flashcards.isLoading}
                      isGenerating={flashcards.isGenerating}
                      error={flashcards.error}
                      statusError={flashcards.statusError}
                      isActive={activeTab === "flashcards"}
                      onGenerate={flashcards.generate}
                      onSetStatus={flashcards.setCardStatus}
                      onReload={() => void flashcards.reload()}
                    />
                  ) : null}

                  {tab === "quiz" ? (
                    <QuizPanel
                      document={selected}
                      quiz={quiz.quiz}
                      isLoading={quiz.isLoading}
                      isGenerating={quiz.isGenerating}
                      error={quiz.error}
                      isActive={activeTab === "quiz"}
                      onGenerate={quiz.generate}
                      onReload={() => void quiz.reload()}
                    />
                  ) : null}
                </div>
              ))}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
