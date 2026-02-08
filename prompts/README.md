# CupidsShield Prompt Library

Comprehensive prompt templates for Trust & Safety operations.

## Purpose

This prompt library provides detailed guidance for both AI agents and human moderators when evaluating content. Each prompt includes:
- Policy definitions
- Red flag indicators
- Severity classifications
- Analysis frameworks
- Decision criteria

## Moderation Prompts

Located in `prompts/moderation/`

### 1. Harassment Detection
**File**: `harassment_detection.txt`

**Use for**: Threats, bullying, hate speech, stalking behavior

**Key features**:
- Severity levels (low → critical)
- Context considerations (first message vs. ongoing harassment)
- Real-world threat assessment
- Stalking behavior identification

**When to use**:
- User reports of threatening messages
- Automated flags for violent language
- Persistent unwanted contact patterns
- Hate speech detection

---

### 2. Scam Detection (Pig Butchering Focus)
**File**: `scam_detection.txt`

**Use for**: Romance scams, financial fraud, pig butchering schemes

**Key features**:
- Pig butchering pattern recognition (romance → financial request)
- Stage identification (grooming, setup, execution)
- Off-platform migration red flags
- Investment scam indicators

**Dating-specific patterns**:
- Rapid intimacy ("I love you" too soon)
- Financial requests (crypto, gift cards, emergency money)
- Reluctance to meet in person
- Moving to WhatsApp/Telegram quickly

**When to use**:
- Messages mentioning money or investments
- Requests to leave platform
- Sob stories or emergencies
- Crypto/trading discussions

---

### 3. Fake Profile Analysis
**File**: `fake_profile_analysis.txt`

**Use for**: Catfishing, stolen photos, fake identities, verification evasion

**Key features**:
- Photo authenticity assessment
- Consistency checking (bio vs. photos vs. behavior)
- Stock photo detection
- Profile type classification (catfish, scammer, misrepresentation)

**Red flags**:
- Professional/stock photography
- Too-good-to-be-true details
- Inconsistent information
- Celebrity or model photos

**When to use**:
- Profile creation review
- User reports of fake profiles
- Verification challenges
- Reverse image search hits

---

### 4. Age Verification
**File**: `age_verification_check.txt`

**Use for**: Potential underage users (platform is 18+)

**Key features**:
- High school reference detection
- Age admission patterns
- Photo age assessment
- Zero-tolerance policy guidance

**Critical indicators**:
- High school mentions (prom, homecoming, SATs)
- "Just turned 18" claims
- Parent references (in teenage context)
- Admission of being under 18

**When to use**:
- Youthful-appearing profiles
- High school references in bio
- Recent 18th birthday claims
- Evasive age responses

**Priority**: HIGHEST - child safety is non-negotiable

---

## Appeals Prompts

Located in `prompts/appeals/`

### 5. Appeal Review
**File**: `appeal_review.txt`

**Use for**: Comprehensive appeal evaluation

**Key features**:
- 4-criteria weighted evaluation framework
- Decision guidance (overturn/uphold/escalate)
- Fairness principles
- Precedent considerations

**Evaluation criteria**:
1. **New Evidence** (40%): Substantial new information?
2. **Policy Misinterpretation** (30%): Was policy misapplied?
3. **User Explanation** (20%): Compelling context provided?
4. **User History** (10%): First-time vs. repeat offender?

**When to use**:
- User files appeal
- Initial appeal assessment
- Senior moderator reviews
- Policy precedent cases

---

### 6. Evidence Evaluation
**File**: `evidence_evaluation.txt`

**Use for**: Assessing new evidence in appeals

**Key features**:
- Evidence type classification
- Authenticity assessment
- Credibility scoring
- Fabrication detection

**Evidence types**:
- **Strong**: Screenshots, login logs, verification docs
- **Moderate**: Partial context, character references
- **Weak**: Assertions without proof, irrelevant information

**Red flags**:
- Edited screenshots
- Convenient "perfect" evidence
- Timing issues
- Contradictions

**When to use**:
- Appeals with new evidence
- Account compromise claims
- Context dispute cases
- Technical error claims

---

## How to Use This Library

### For AI Agents

Agents automatically incorporate relevant prompts during their workflows:
- **Moderation Agent**: Uses violation-specific prompts during risk assessment
- **Appeals Agent**: Uses appeals prompts during evaluation

Prompts are loaded dynamically based on detected violation type.

### For Human Moderators

1. **Review Queue**: When reviewing flagged content, reference the appropriate prompt
2. **Quality Assurance**: Use prompts to ensure consistency across moderators
3. **Training**: New moderators should study all prompts thoroughly
4. **Edge Cases**: When uncertain, consult prompts for guidance

### For Policy Team

- **Updates**: Modify prompts when policies change
- **Calibration**: Use prompts to align moderator decision-making
- **Metrics**: Track how often each severity level is applied
- **Iteration**: Update based on appeal overturn patterns

## Prompt Engineering Best Practices

### Structure
Each prompt follows this structure:
1. **Policy statement**: Clear definition of the violation
2. **Red flags**: Specific indicators to watch for
3. **Severity levels**: Classification framework
4. **Context considerations**: Nuance and edge cases
5. **Analysis format**: Structured output template

### Tone
- Authoritative but fair
- Detailed and specific
- Action-oriented
- Safety-focused while respecting user rights

### Updates
When updating prompts:
1. Test changes on historical cases
2. Measure impact on accuracy metrics
3. Document changes in version control
4. Retrain agents and moderators
5. Monitor for unintended consequences

## Metrics & Monitoring

Track prompt effectiveness:
- **Accuracy**: Agent decisions vs. human review
- **Consistency**: Similar cases → similar outcomes
- **Appeal rate**: How often decisions are appealed
- **Overturn rate**: How often appeals succeed
- **False positive rate**: Incorrect violation flags
- **False negative rate**: Missed violations

## Versioning

Prompts are version-controlled alongside code. When making changes:
- Tag versions for reproducibility
- Document rationale for changes
- A/B test significant modifications
- Maintain backwards compatibility during transitions

## Related Documentation

- **Policy Playbook**: `docs/policy_playbook.md` - Detailed policy explanations
- **Operator Guide**: `docs/operator_guide.md` - How to use the review queue
- **Configuration**: `config/moderation_config.yaml` - Thresholds and actions

## Questions?

For prompt-related questions:
- Policy Team: Policy interpretation and updates
- Engineering Team: Agent integration and performance
- Operations Team: Real-world application and edge cases

---

**Last Updated**: 2024
**Version**: 1.0
**Owner**: Trust & Safety Team
