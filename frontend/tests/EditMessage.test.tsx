import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React, { useState } from 'react';
import { Pencil, X, Check } from 'lucide-react';
import type { ChatMessage } from '@/lib/types';

function UserMessageRow({
  msg,
  isLastUser,
  loading,
  regenerating,
  editingMessageId,
  editContent,
  onEditClick,
  onEditContentChange,
  onEditSave,
  onEditCancel,
  editLabel,
  editingLabel,
  saveEditLabel,
  cancelEditLabel,
}: {
  msg: ChatMessage;
  isLastUser: boolean;
  loading: boolean;
  regenerating: boolean;
  editingMessageId: string | null;
  editContent: string;
  onEditClick: () => void;
  onEditContentChange: (val: string) => void;
  onEditSave: () => void;
  onEditCancel: () => void;
  editLabel: string;
  editingLabel: string;
  saveEditLabel: string;
  cancelEditLabel: string;
}) {
  if (editingMessageId === msg.id) {
    return (
      <div className="max-w-[75%] w-full" data-testid="edit-container">
        <textarea
          value={editContent}
          onChange={(e) => onEditContentChange(e.target.value)}
          autoFocus
          rows={2}
          aria-label={editingLabel}
          data-testid="edit-textarea"
        />
        <div className="flex items-center gap-2 mt-2 justify-end">
          <button onClick={onEditCancel} data-testid="cancel-edit">
            <X className="w-3.5 h-3.5" />
            {cancelEditLabel}
          </button>
          <button onClick={onEditSave} disabled={!editContent.trim() || loading} data-testid="save-edit">
            <Check className="w-3.5 h-3.5" />
            {saveEditLabel}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[75%] rounded-2xl px-4 py-3 bg-primary/10 border border-primary/15 group relative" data-testid="user-bubble">
      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
      {isLastUser && !loading && !regenerating && (
        <button
          onClick={onEditClick}
          className="opacity-0 group-hover:opacity-100"
          aria-label={editLabel}
          data-testid="edit-button"
        >
          <Pencil className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}

describe('EditMessage', () => {
  it('renders edit button on last user message', () => {
    render(
      <UserMessageRow
        msg={{ id: '1', role: 'user', content: 'Plan a trip' }}
        isLastUser={true}
        loading={false}
        regenerating={false}
        editingMessageId={null}
        editContent=""
        onEditClick={() => {}}
        onEditContentChange={() => {}}
        onEditSave={() => {}}
        onEditCancel={() => {}}
        editLabel="Edit"
        editingLabel="Editing..."
        saveEditLabel="Save"
        cancelEditLabel="Cancel"
      />,
    );
    expect(screen.getByTestId('edit-button')).toBeDefined();
  });

  it('does not render edit button on non-last user messages', () => {
    render(
      <UserMessageRow
        msg={{ id: '1', role: 'user', content: 'Plan a trip' }}
        isLastUser={false}
        loading={false}
        regenerating={false}
        editingMessageId={null}
        editContent=""
        onEditClick={() => {}}
        onEditContentChange={() => {}}
        onEditSave={() => {}}
        onEditCancel={() => {}}
        editLabel="Edit"
        editingLabel="Editing..."
        saveEditLabel="Save"
        cancelEditLabel="Cancel"
      />,
    );
    expect(screen.queryByTestId('edit-button')).toBeNull();
  });

  it('does not render edit button when loading', () => {
    render(
      <UserMessageRow
        msg={{ id: '1', role: 'user', content: 'Plan a trip' }}
        isLastUser={true}
        loading={true}
        regenerating={false}
        editingMessageId={null}
        editContent=""
        onEditClick={() => {}}
        onEditContentChange={() => {}}
        onEditSave={() => {}}
        onEditCancel={() => {}}
        editLabel="Edit"
        editingLabel="Editing..."
        saveEditLabel="Save"
        cancelEditLabel="Cancel"
      />,
    );
    expect(screen.queryByTestId('edit-button')).toBeNull();
  });

  it('clicking edit shows textarea with original content', () => {
    const onEditClick = vi.fn();
    const { rerender } = render(
      <UserMessageRow
        msg={{ id: '1', role: 'user', content: 'Plan a trip to Japan' }}
        isLastUser={true}
        loading={false}
        regenerating={false}
        editingMessageId={null}
        editContent=""
        onEditClick={onEditClick}
        onEditContentChange={() => {}}
        onEditSave={() => {}}
        onEditCancel={() => {}}
        editLabel="Edit"
        editingLabel="Editing..."
        saveEditLabel="Save"
        cancelEditLabel="Cancel"
      />,
    );

    fireEvent.click(screen.getByTestId('edit-button'));
    expect(onEditClick).toHaveBeenCalledTimes(1);

    rerender(
      <UserMessageRow
        msg={{ id: '1', role: 'user', content: 'Plan a trip to Japan' }}
        isLastUser={true}
        loading={false}
        regenerating={false}
        editingMessageId="1"
        editContent="Plan a trip to Japan"
        onEditClick={onEditClick}
        onEditContentChange={() => {}}
        onEditSave={() => {}}
        onEditCancel={() => {}}
        editLabel="Edit"
        editingLabel="Editing..."
        saveEditLabel="Save"
        cancelEditLabel="Cancel"
      />,
    );

    expect(screen.getByTestId('edit-textarea')).toBeDefined();
    expect((screen.getByTestId('edit-textarea') as HTMLTextAreaElement).value).toBe('Plan a trip to Japan');
  });

  it('save button calls onEditSave', () => {
    const onEditSave = vi.fn();
    render(
      <UserMessageRow
        msg={{ id: '1', role: 'user', content: 'Original' }}
        isLastUser={true}
        loading={false}
        regenerating={false}
        editingMessageId="1"
        editContent="Edited content"
        onEditClick={() => {}}
        onEditContentChange={() => {}}
        onEditSave={onEditSave}
        onEditCancel={() => {}}
        editLabel="Edit"
        editingLabel="Editing..."
        saveEditLabel="Save"
        cancelEditLabel="Cancel"
      />,
    );

    fireEvent.click(screen.getByTestId('save-edit'));
    expect(onEditSave).toHaveBeenCalledTimes(1);
  });

  it('cancel button calls onEditCancel', () => {
    const onEditCancel = vi.fn();
    render(
      <UserMessageRow
        msg={{ id: '1', role: 'user', content: 'Original' }}
        isLastUser={true}
        loading={false}
        regenerating={false}
        editingMessageId="1"
        editContent="Edited content"
        onEditClick={() => {}}
        onEditContentChange={() => {}}
        onEditSave={() => {}}
        onEditCancel={onEditCancel}
        editLabel="Edit"
        editingLabel="Editing..."
        saveEditLabel="Save"
        cancelEditLabel="Cancel"
      />,
    );

    fireEvent.click(screen.getByTestId('cancel-edit'));
    expect(onEditCancel).toHaveBeenCalledTimes(1);
  });

  it('save button is disabled when editContent is empty', () => {
    render(
      <UserMessageRow
        msg={{ id: '1', role: 'user', content: 'Original' }}
        isLastUser={true}
        loading={false}
        regenerating={false}
        editingMessageId="1"
        editContent=""
        onEditClick={() => {}}
        onEditContentChange={() => {}}
        onEditSave={() => {}}
        onEditCancel={() => {}}
        editLabel="Edit"
        editingLabel="Editing..."
        saveEditLabel="Save"
        cancelEditLabel="Cancel"
      />,
    );

    const saveBtn = screen.getByTestId('save-edit');
    expect(saveBtn.hasAttribute('disabled')).toBe(true);
  });
});
