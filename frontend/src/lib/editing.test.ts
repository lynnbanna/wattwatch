import { describe, expect, it } from "vitest";
import {
  countEdits,
  editorReducer,
  initialEditorState,
  midpoint,
  type EditorState,
  type Region,
} from "./editing";

const square: Region = {
  id: "roof-0",
  kind: "roof",
  label: "roof",
  polygon: [
    [0, 0],
    [10, 0],
    [10, 10],
    [0, 10],
  ],
  source: "model",
  modelScore: 0.9,
};

const start = (): EditorState => initialEditorState([square]);

describe("editorReducer", () => {
  it("moves a vertex and marks the region as edited", () => {
    const s = editorReducer(start(), { type: "moveVertex", id: "roof-0", index: 1, point: [12, 0] });
    expect(s.regions[0].polygon[1]).toEqual([12, 0]);
    expect(s.regions[0].source).toBe("edited");
  });

  it("undoes a whole drag in one step via checkpoint", () => {
    let s = editorReducer(start(), { type: "checkpoint" });
    s = editorReducer(s, { type: "moveVertex", id: "roof-0", index: 1, point: [11, 0] });
    s = editorReducer(s, { type: "moveVertex", id: "roof-0", index: 1, point: [12, 0] });
    s = editorReducer(s, { type: "undo" });
    expect(s.regions[0]).toEqual(square);
  });

  it("inserts a vertex after the given index", () => {
    const s = editorReducer(start(), {
      type: "insertVertex",
      id: "roof-0",
      afterIndex: 0,
      point: [5, -2],
    });
    expect(s.regions[0].polygon).toHaveLength(5);
    expect(s.regions[0].polygon[1]).toEqual([5, -2]);
  });

  it("removes a vertex but never below three points", () => {
    let s = editorReducer(start(), { type: "removeVertex", id: "roof-0", index: 3 });
    expect(s.regions[0].polygon).toHaveLength(3);
    s = editorReducer(s, { type: "removeVertex", id: "roof-0", index: 0 });
    expect(s.regions[0].polygon).toHaveLength(3);
  });

  it("deletes a region, clears selection, and undo restores it", () => {
    let s = editorReducer(start(), { type: "select", id: "roof-0" });
    s = editorReducer(s, { type: "deleteRegion", id: "roof-0" });
    expect(s.regions).toHaveLength(0);
    expect(s.selectedId).toBeNull();
    s = editorReducer(s, { type: "undo" });
    expect(s.regions).toEqual([square]);
  });

  it("adds a drawn region only once it has three points", () => {
    let s = editorReducer(start(), { type: "startDraft", kind: "obstacle" });
    s = editorReducer(s, { type: "addDraftPoint", point: [1, 1] });
    s = editorReducer(s, { type: "addDraftPoint", point: [3, 1] });
    expect(editorReducer(s, { type: "finishDraft" }).regions).toHaveLength(1);
    s = editorReducer(s, { type: "addDraftPoint", point: [3, 3] });
    s = editorReducer(s, { type: "finishDraft" });
    expect(s.regions).toHaveLength(2);
    expect(s.regions[1]).toMatchObject({ kind: "obstacle", source: "added", modelScore: null });
    expect(s.selectedId).toBe(s.regions[1].id);
    expect(s.draft).toBeNull();
  });

  it("load replaces regions and clears history", () => {
    let s = editorReducer(start(), { type: "deleteRegion", id: "roof-0" });
    s = editorReducer(s, { type: "load", regions: [square] });
    expect(s.regions).toEqual([square]);
    expect(s.history).toEqual([]);
  });

  it("ignores undo with no history", () => {
    const s = start();
    expect(editorReducer(s, { type: "undo" })).toBe(s);
  });
});

describe("helpers", () => {
  it("midpoint", () => {
    expect(midpoint([0, 0], [10, 4])).toEqual([5, 2]);
  });

  it("counts edited, added and deleted regions", () => {
    const original = [square, { ...square, id: "obstacle-0", kind: "obstacle" as const }];
    const edited: Region[] = [
      { ...square, source: "edited" },
      { ...square, id: "added-1", source: "added", modelScore: null },
    ];
    expect(countEdits(edited, original)).toBe(3);
    expect(countEdits(original, original)).toBe(0);
  });
});
