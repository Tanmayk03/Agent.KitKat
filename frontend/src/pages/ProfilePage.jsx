import React, { useState, useEffect } from 'react';
import {
  User,
  GraduationCap,
  Briefcase,
  MapPin,
  Save,
  Check,
  ShieldCheck,
  AlertCircle,
  Plus,
  X,
} from 'lucide-react';
import { api } from '../services/api';

export default function ProfilePage({ profile, onProfileUpdated }) {
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    location: '',
    linkedin_url: '',
    github_url: '',
    portfolio_url: '',
    education: {
      degree: 'B.Tech',
      specialization: 'Computer Science and Data Science',
      college: 'SRM University, Delhi NCR',
      cgpa: 8.44,
      graduation: 'May 2027',
      graduation_year: 2027,
    },
    preferred_roles: [],
    preferred_locations: [],
    application_preferences: {
      daily_search_time: '09:00',
      max_applications_per_day: 5,
      min_match_score: 75,
      submission_policy: 'manual_approval',
    },
  });

  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [newRole, setNewRole] = useState('');
  const [newLocation, setNewLocation] = useState('');

  useEffect(() => {
    if (profile) {
      setFormData({
        full_name: profile.full_name || '',
        email: profile.email || '',
        phone: profile.phone || '',
        location: profile.location || 'India',
        linkedin_url: profile.linkedin_url || '',
        github_url: profile.github_url || '',
        portfolio_url: profile.portfolio_url || '',
        education: profile.education || {},
        preferred_roles: profile.preferred_roles || [],
        preferred_locations: profile.preferred_locations || [],
        application_preferences: profile.application_preferences || {},
      });
    }
  }, [profile]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      const updated = await api.updateProfile(formData);
      onProfileUpdated(updated);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2500);
    } catch (err) {
      alert(`Failed to update profile: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const addRole = () => {
    if (newRole.trim() && !formData.preferred_roles.includes(newRole.trim())) {
      setFormData({
        ...formData,
        preferred_roles: [...formData.preferred_roles, newRole.trim()],
      });
      setNewRole('');
    }
  };

  const removeRole = (role) => {
    setFormData({
      ...formData,
      preferred_roles: formData.preferred_roles.filter((r) => r !== role),
    });
  };

  const addLocation = () => {
    if (newLocation.trim() && !formData.preferred_locations.includes(newLocation.trim())) {
      setFormData({
        ...formData,
        preferred_locations: [...formData.preferred_locations, newLocation.trim()],
      });
      setNewLocation('');
    }
  };

  const removeLocation = (loc) => {
    setFormData({
      ...formData,
      preferred_locations: formData.preferred_locations.filter((l) => l !== loc),
    });
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div>
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-mono bg-amber-500/10 border border-amber-500/20 text-amber-300 mb-2">
          <span>Personal Career Profile (Ground Truth)</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Candidate Profile & Eligibility Baseline
        </h1>
        <p className="text-sm text-slate-400">
          Agent KitKat strictly grounds all eligibility checks, cover letters, and form fills in this profile. Zero hallucinations.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Contact Information */}
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4 shadow-xl">
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <User className="w-4 h-4 text-amber-400" />
            <span>Contact Information</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Full Name</label>
              <input
                type="text"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Email Address</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Phone Number</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Current Location</label>
              <input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">LinkedIn URL</label>
              <input
                type="url"
                value={formData.linkedin_url}
                onChange={(e) => setFormData({ ...formData, linkedin_url: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500 font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">GitHub URL</label>
              <input
                type="url"
                value={formData.github_url}
                onChange={(e) => setFormData({ ...formData, github_url: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500 font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Portfolio URL</label>
              <input
                type="url"
                value={formData.portfolio_url}
                onChange={(e) => setFormData({ ...formData, portfolio_url: e.target.value })}
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500 font-mono text-xs"
              />
            </div>
          </div>
        </div>

        {/* Education Details */}
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4 shadow-xl">
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <GraduationCap className="w-4 h-4 text-amber-400" />
            <span>Academic Qualifications</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Degree</label>
              <input
                type="text"
                value={formData.education.degree || 'B.Tech'}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    education: { ...formData.education, degree: e.target.value },
                  })
                }
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Specialization / Major</label>
              <input
                type="text"
                value={formData.education.specialization || 'Computer Science and Data Science'}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    education: { ...formData.education, specialization: e.target.value },
                  })
                }
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">College / University</label>
              <input
                type="text"
                value={formData.education.college || 'SRM University, Delhi NCR'}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    education: { ...formData.education, college: e.target.value },
                  })
                }
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">CGPA</label>
              <input
                type="number"
                step="0.01"
                value={formData.education.cgpa || 8.44}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    education: { ...formData.education, cgpa: parseFloat(e.target.value) || 0.0 },
                  })
                }
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Graduation Year</label>
              <input
                type="number"
                value={formData.education.graduation_year || 2027}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    education: { ...formData.education, graduation_year: parseInt(e.target.value) || 2027 },
                  })
                }
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Graduation Month & Year</label>
              <input
                type="text"
                value={formData.education.graduation || 'May 2027'}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    education: { ...formData.education, graduation: e.target.value },
                  })
                }
                className="w-full px-3.5 py-2 rounded-xl bg-slate-800/80 border border-slate-700 text-sm text-white focus:outline-none focus:border-amber-500"
              />
            </div>
          </div>
        </div>

        {/* Verified vs Unverified Skills */}
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4 shadow-xl">
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Skills Verification Status</span>
          </h2>
          <p className="text-xs text-slate-400">
            Skills are automatically verified when you upload your resume. Unverified skills will not be claimed without confirmation.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            {/* Verified Skills */}
            <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20 space-y-2">
              <span className="text-xs font-semibold text-emerald-400 flex items-center space-x-1.5">
                <Check className="w-3.5 h-3.5" />
                <span>Verified by Active Resume ({profile?.verified_skills?.length || 0})</span>
              </span>
              <div className="flex flex-wrap gap-1.5">
                {profile?.verified_skills?.map((s, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-md text-xs font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                  >
                    {s}
                  </span>
                ))}
                {(!profile?.verified_skills || profile.verified_skills.length === 0) && (
                  <span className="text-xs text-slate-500">Upload a resume to verify skills.</span>
                )}
              </div>
            </div>

            {/* Unverified Skills */}
            <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-2">
              <span className="text-xs font-semibold text-amber-400 flex items-center space-x-1.5">
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Pending Verification ({profile?.unverified_skills?.length || 0})</span>
              </span>
              <div className="flex flex-wrap gap-1.5">
                {profile?.unverified_skills?.map((s, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-md text-xs font-mono bg-amber-500/10 text-amber-300 border border-amber-500/20"
                  >
                    {s}
                  </span>
                ))}
                {(!profile?.unverified_skills || profile.unverified_skills.length === 0) && (
                  <span className="text-xs text-slate-500">All skills verified!</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Preferred Roles & Locations */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          {/* Roles */}
          <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4 shadow-xl">
            <h2 className="text-base font-bold text-white flex items-center space-x-2">
              <Briefcase className="w-4 h-4 text-amber-400" />
              <span>Preferred Job Roles</span>
            </h2>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. AI/ML Intern"
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addRole())}
                className="flex-1 px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700 text-xs text-white focus:outline-none focus:border-amber-500"
              />
              <button
                type="button"
                onClick={addRole}
                className="p-2 rounded-xl bg-amber-500 text-slate-950 font-bold hover:bg-amber-400 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {formData.preferred_roles.map((r, i) => (
                <span
                  key={i}
                  className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs bg-slate-800 text-slate-200 border border-slate-700"
                >
                  <span>{r}</span>
                  <button type="button" onClick={() => removeRole(r)} className="hover:text-rose-400">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>

          {/* Locations */}
          <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 space-y-4 shadow-xl">
            <h2 className="text-base font-bold text-white flex items-center space-x-2">
              <MapPin className="w-4 h-4 text-amber-400" />
              <span>Preferred Locations</span>
            </h2>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. Bangalore"
                value={newLocation}
                onChange={(e) => setNewLocation(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addLocation())}
                className="flex-1 px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700 text-xs text-white focus:outline-none focus:border-amber-500"
              />
              <button
                type="button"
                onClick={addLocation}
                className="p-2 rounded-xl bg-amber-500 text-slate-950 font-bold hover:bg-amber-400 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {formData.preferred_locations.map((loc, i) => (
                <span
                  key={i}
                  className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs bg-slate-800 text-slate-200 border border-slate-700"
                >
                  <span>{loc}</span>
                  <button type="button" onClick={() => removeLocation(loc)} className="hover:text-rose-400">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Submit Bar */}
        <div className="pt-2 flex items-center space-x-4">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center space-x-2 px-6 py-2.5 rounded-xl text-sm font-semibold bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-md shadow-amber-500/20 active:scale-95 transition-all disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving...' : 'Save Profile Changes'}</span>
          </button>

          {success && (
            <span className="text-xs font-semibold text-emerald-400 flex items-center space-x-1">
              <Check className="w-4 h-4" />
              <span>Profile updated successfully!</span>
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
