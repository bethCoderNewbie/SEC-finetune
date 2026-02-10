# Plan: [Feature/Bugfix Name]

## Desired End State
[A clear specification of the desired end state after this plan is complete]
* [Feature capability 1]
* [Feature capability 2]
* [Validation rule or constraint]

### Key Discoveries
* [Important finding with file:line reference]
* [Pattern or convention to follow]
* [Constraint to work within]

## What We're NOT Doing
[Explicitly list out-of-scope items to prevent scope creep]
* [Out of scope item 1]
* [Out of scope item 2]

## Implementation Approach
[High-level strategy and reasoning, e.g., "Start with backend infrastructure... then build UI components"]

---

## Phase 1: [Descriptive Name, e.g., Backend Infrastructure]
**Overview:** [What this phase accomplishes]

### Changes Required:

**1. [Component Name]**
**File:** `path/to/file.ts` (new file/modification)
**Changes:** [Description of change]

```typescript
// Insert specific code snippet or interface definition here
interface ExampleProps {
  directories: string[];
}
Based on the structure outlined in the system instructions and the example plan provided in the images, here is the Markdown template for the **Plan Document**.

### **Plan Document Template**

````markdown
# Plan: [Feature/Bugfix Name]

## Desired End State
[A clear specification of the desired end state after this plan is complete]
* [Feature capability 1]
* [Feature capability 2]
* [Validation rule or constraint]

### Key Discoveries
* [Important finding with file:line reference]
* [Pattern or convention to follow]
* [Constraint to work within]

## What We're NOT Doing
[Explicitly list out-of-scope items to prevent scope creep]
* [Out of scope item 1]
* [Out of scope item 2]

## Implementation Approach
[High-level strategy and reasoning, e.g., "Start with backend infrastructure... then build UI components"]

---

## Phase 1: [Descriptive Name, e.g., Backend Infrastructure]
**Overview:** [What this phase accomplishes]

### Changes Required:

**1. [Component Name]**
**File:** `path/to/file.ts` (new file/modification)
**Changes:** [Description of change]

```typescript
// Insert specific code snippet or interface definition here
interface ExampleProps {
  directories: string[];
}
````

**2. [Database Schema/Another Component]**
**File:** `path/to/schema.go`
**Changes:** [Description, e.g., "Add migration for column"]

```go
// Insert code changes
alterations := []struct {
  column string
  sql    string
}{
  {"additional_directories", "ALTER TABLE sessions ADD COLUMN..."},
}
```

## Phase 2: [Descriptive Name, e.g., UI Implementation]

[Repeat structure for next phase]

## Success Criteria

### Automated Verification:

[List specific commands to verify the build]

  - [ ] TypeScript compilation: `make -C project check`
  - [ ] Linting passes: `make -C project lint`
  - [ ] Tests pass: `make -C project test`

### Manual Verification:

[List specific user actions to test]

  - [ ] Can [perform action 1] via UI
  - [ ] Validation works (e.g., non-existent paths are rejected)

<!-- end list -->

```
```